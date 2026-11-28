"""Pure-stdlib YouTube OAuth2 loopback + PKCE refresh token utility."""

from __future__ import annotations

import base64
import hashlib
import html
import http.server
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
YOUTUBE_WRITE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
)
YOUTUBE_OAUTH_SCOPES = (
    *YOUTUBE_WRITE_SCOPES,
    "https://www.googleapis.com/auth/youtube.readonly",
)
DEFAULT_CALLBACK_TIMEOUT_SECONDS = 300


class OAuthRefreshError(RuntimeError):
    """Raised when OAuth credential loading, loopback callback, or token exchange fails."""


def parse_env_content(content: str) -> dict[str, str]:
    """Parse `.env` file text into a key-value dict without mutating `os.environ`."""
    values: dict[str, str] = {}

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if raw_value and raw_value[0] in ("'", '"'):
            quote = raw_value[0]
            end_idx = raw_value.find(quote, 1)
            if end_idx != -1:
                value = raw_value[1:end_idx]
            else:
                value = raw_value.split("#", 1)[0].strip()
        else:
            value = raw_value.split("#", 1)[0].strip()

        values[key] = value

    return values


def read_env_file(path: Path) -> tuple[str, dict[str, str]]:
    """Read an env file without mutating process environment; fail closed if missing."""
    if not path.is_file():
        raise OAuthRefreshError(f"Environment file not found: {path}")

    content = path.read_text(encoding="utf-8-sig")
    return content, parse_env_content(content)


def load_oauth_client_credentials(env_file: Path) -> tuple[str, str, str]:
    """Load and validate YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET from env_file."""
    content, env = read_env_file(env_file)
    client_id = env.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = env.get("YOUTUBE_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise OAuthRefreshError(
            f"YOUTUBE_CLIENT_ID and/or YOUTUBE_CLIENT_SECRET are missing in {env_file}"
        )

    return content, client_id, client_secret


def update_refresh_token(path: Path, content: str, token: str) -> None:
    """Atomically update ONLY YOUTUBE_REFRESH_TOKEN in path, preserving all other lines."""
    clean_token = token.strip() if isinstance(token, str) else ""
    if not clean_token:
        raise OAuthRefreshError("Refusing to write an empty YOUTUBE_REFRESH_TOKEN.")
    if any(ch in clean_token for ch in ("\n", "\r", '"')):
        raise OAuthRefreshError("Refusing to write YOUTUBE_REFRESH_TOKEN containing invalid control or quote characters.")

    lines = content.splitlines(keepends=True)
    replacement = f'YOUTUBE_REFRESH_TOKEN="{clean_token}"'
    found = False

    for index, line in enumerate(lines):
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        export_prefix = ""
        key_part = stripped
        if key_part.startswith("export "):
            export_prefix = "export "
            key_part = key_part[7:].lstrip()

        key = key_part.split("=", 1)[0].strip()
        if key == "YOUTUBE_REFRESH_TOKEN":
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = indent + export_prefix + replacement + ending
            found = True
            break

    if not found:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(replacement + "\n")

    updated = "".join(lines)
    temp_path = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        temp_path.write_text(updated, encoding="utf-8", newline="")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a (code_verifier, code_challenge) S256 PKCE pair."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scopes: tuple[str, ...] = YOUTUBE_OAUTH_SCOPES,
) -> str:
    """Build Google OAuth2 authorization URL with offline access and forced consent."""
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


def make_callback_handler(
    expected_state: str,
    result: dict[str, str],
    completed: threading.Event,
) -> type[http.server.BaseHTTPRequestHandler]:
    """Create a stateful-isolated loopback HTTP handler for a single OAuth callback."""

    class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/":
                self.send_error(404)
                return

            params = urllib.parse.parse_qs(parsed.query)
            returned_state = params.get("state", [""])[0]
            if not secrets.compare_digest(returned_state, expected_state):
                result["error"] = (
                    "OAuth state validation failed. Do not use this authorization result."
                )
                self._respond("Authorization failed", result["error"])
                completed.set()
                return

            if "error" in params:
                result["error"] = params["error"][0]
                result["error_description"] = params.get("error_description", [""])[0]
                self._respond("Authorization was not completed", result["error"])
                completed.set()
                return

            code = params.get("code", [""])[0]
            if not code:
                result["error"] = "Google returned no authorization code."
                self._respond("Authorization failed", result["error"])
                completed.set()
                return

            result["code"] = code
            self._respond(
                "Authorization received",
                "Google authorization was received. You can return to the terminal.",
            )
            completed.set()

        def _respond(self, title: str, message: str) -> None:
            safe_title = html.escape(title)
            safe_message = html.escape(message)
            body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{safe_title}</title></head><body>"
                f"<h2>{safe_title}</h2><p>{safe_message}</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            # Never log callback URLs: they contain short-lived authorization codes.
            return

    return _OAuthCallbackHandler


def exchange_authorization_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
    *,
    timeout: int = 30,
    urlopen_fn: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """Exchange an authorization code + PKCE verifier for OAuth2 tokens."""
    urlopen_impl = urlopen_fn or urllib.request.urlopen
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen_impl(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_details = exc.read().decode("utf-8", errors="replace")
        summary = raw_details[:300]
        try:
            err_json = json.loads(raw_details)
            if isinstance(err_json, dict) and err_json.get("error"):
                err_code = str(err_json["error"])
                err_desc = str(err_json.get("error_description", "")).strip()
                summary = f"{err_code}: {err_desc}".rstrip(": ")
        except Exception:
            pass
        raise OAuthRefreshError(
            f"Google token exchange failed (HTTP {exc.code}): {summary}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OAuthRefreshError(
            f"Could not reach Google's token endpoint: {exc.reason}"
        ) from exc


def run_oauth_refresh_flow(
    env_file: Path,
    *,
    timeout_seconds: int = DEFAULT_CALLBACK_TIMEOUT_SECONDS,
    open_browser_fn: Optional[Callable[[str], bool]] = None,
    urlopen_fn: Optional[Callable[..., Any]] = None,
    on_auth_url: Optional[Callable[[str], None]] = None,
) -> Path:
    """Run loopback OAuth2 + PKCE flow and atomically store YOUTUBE_REFRESH_TOKEN in env_file."""
    if timeout_seconds <= 0:
        raise OAuthRefreshError("OAuth callback timeout_seconds must be greater than 0.")
    open_browser_impl = open_browser_fn or webbrowser.open
    original_content, client_id, client_secret = load_oauth_client_credentials(env_file)

    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    result: dict[str, str] = {}
    completed = threading.Event()
    handler_cls = make_callback_handler(state, result, completed)

    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    try:
        server.timeout = min(1.0, float(timeout_seconds)) if timeout_seconds > 0 else 0.1
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/"
        authorization_url = build_authorization_url(client_id, redirect_uri, state, challenge)

        if on_auth_url is not None:
            on_auth_url(authorization_url)

        open_browser_impl(authorization_url)

        deadline = time.monotonic() + timeout_seconds
        while not completed.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if "error" in result:
        description = result.get("error_description", "")
        raise OAuthRefreshError(
            f"OAuth authorization failed: {result['error']} {description}".strip()
        )
    if "code" not in result:
        raise OAuthRefreshError(
            f"No OAuth callback received within {timeout_seconds} seconds."
        )

    tokens = exchange_authorization_code(
        result["code"],
        redirect_uri,
        client_id,
        client_secret,
        verifier,
        urlopen_fn=urlopen_fn,
    )
    refresh_token = tokens.get("refresh_token")

    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise OAuthRefreshError(
            f"Google did not return a refresh_token. The existing {env_file.name} was not changed. "
            "Try revoking this app's access at https://myaccount.google.com/connections, "
            "then run this script again and grant consent."
        )

    update_refresh_token(env_file, original_content, refresh_token.strip())
    return env_file
