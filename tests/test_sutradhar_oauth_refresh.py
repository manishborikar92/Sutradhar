#!/usr/bin/env python3
"""Offline unit and integration tests for Sutradhar's YouTube OAuth refresh utility."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import refresh_youtube_token  # noqa: E402
from sutradhar.publishing.oauth_refresh import (  # noqa: E402
    TOKEN_ENDPOINT,
    YOUTUBE_OAUTH_SCOPES,
    YOUTUBE_WRITE_SCOPES,
    OAuthRefreshError,
    exchange_authorization_code,
    load_oauth_client_credentials,
    parse_env_content,
    run_oauth_refresh_flow,
    update_refresh_token,
)
from sutradhar.publishing.youtube_client import (  # noqa: E402
    build_youtube_client,
    load_env_file,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_missing_env_file_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / ".env.local"
    with pytest.raises(OAuthRefreshError, match="Environment file not found"):
        load_oauth_client_credentials(missing)


@pytest.mark.parametrize(
    "content",
    [
        'YOUTUBE_CLIENT_SECRET="dummy-secret"\n',
        'YOUTUBE_CLIENT_ID="dummy-client-id"\n',
        'YOUTUBE_CLIENT_ID=""\nYOUTUBE_CLIENT_SECRET="dummy-secret"\n',
        'YOUTUBE_CLIENT_ID="dummy-client-id"\nYOUTUBE_CLIENT_SECRET="   "\n',
    ],
)
def test_missing_client_credentials_fail_closed(tmp_path: Path, content: str) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(content, encoding="utf-8")

    with pytest.raises(OAuthRefreshError, match="YOUTUBE_CLIENT_ID and/or YOUTUBE_CLIENT_SECRET"):
        load_oauth_client_credentials(env_file)


def test_update_refresh_token_updates_in_place_preserving_formatting(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    original = (
        "# Sutradhar secrets\r\n"
        "\r\n"
        'YOUTUBE_CLIENT_ID="client-123.apps.googleusercontent.com"\r\n'
        'YOUTUBE_CLIENT_SECRET="secret-xyz"\r\n'
        'YOUTUBE_REFRESH_TOKEN="old-token"\r\n'
        'YOUTUBE_REFRESH_TOKEN_BACKUP="keep-me-untouched"\r\n'
        "# ElevenLabs\r\n"
        "ELEVENLABS_API_KEY='el-key-999' # inline comment\r\n"
    )
    env_file.write_bytes(original.encode("utf-8"))

    update_refresh_token(env_file, original, "new-token-value")
    updated = env_file.read_bytes().decode("utf-8")

    expected = original.replace('YOUTUBE_REFRESH_TOKEN="old-token"', 'YOUTUBE_REFRESH_TOKEN="new-token-value"')
    assert updated == expected
    assert not list(tmp_path.glob("*.tmp"))


def test_update_refresh_token_appends_cleanly_when_absent(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    original = (
        "# Header comment\n"
        'YOUTUBE_CLIENT_ID="client-123"\n'
        'YOUTUBE_CLIENT_SECRET="secret-xyz"\n'
        'ELEVENLABS_API_KEY="el-key-999"'
    )
    env_file.write_text(original, encoding="utf-8")

    update_refresh_token(env_file, original, "appended-token")
    updated = env_file.read_text(encoding="utf-8")

    assert updated == (
        "# Header comment\n"
        'YOUTUBE_CLIENT_ID="client-123"\n'
        'YOUTUBE_CLIENT_SECRET="secret-xyz"\n'
        'ELEVENLABS_API_KEY="el-key-999"\n'
        'YOUTUBE_REFRESH_TOKEN="appended-token"\n'
    )


def test_run_oauth_refresh_flow_loopback_and_exchange(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    secret_val = "mock-client-secret-never-print"
    refresh_val = "mock-refresh-token-never-print"
    env_file.write_text(
        "# Local env\n"
        'YOUTUBE_CLIENT_ID="mock-client-id"\n'
        f'YOUTUBE_CLIENT_SECRET="{secret_val}"\n'
        'YOUTUBE_REFRESH_TOKEN="stale-token"\n'
        'ELEVENLABS_API_KEY="el-keep"\n',
        encoding="utf-8",
    )

    captured_auth: dict[str, str] = {}
    captured_token_req: dict[str, dict[str, list[str]]] = {}

    def fake_open_browser(auth_url: str) -> bool:
        captured_auth["url"] = auth_url
        parsed = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed.query)
        redirect_uri = params["redirect_uri"][0]
        state = params["state"][0]

        def _hit_callback() -> None:
            # Simulate browser requesting /favicon.ico before the OAuth redirect.
            try:
                urllib.request.urlopen(f"{redirect_uri}favicon.ico", timeout=5)
            except Exception:
                pass
            cb_url = f"{redirect_uri}?{urllib.parse.urlencode({'code': 'auth-code-42', 'state': state})}"
            with urllib.request.urlopen(cb_url, timeout=5) as resp:
                resp.read()

        threading.Thread(target=_hit_callback, daemon=True).start()
        return True

    def fake_urlopen(req: urllib.request.Request, timeout: int = 30) -> _FakeHTTPResponse:
        body = req.data.decode("utf-8") if isinstance(req.data, bytes) else ""
        captured_token_req["form"] = urllib.parse.parse_qs(body)
        return _FakeHTTPResponse({"access_token": "ya29.fake", "refresh_token": refresh_val})

    result_path = run_oauth_refresh_flow(
        env_file,
        timeout_seconds=10,
        open_browser_fn=fake_open_browser,
        urlopen_fn=fake_urlopen,
    )

    assert result_path == env_file

    auth_params = urllib.parse.parse_qs(urllib.parse.urlparse(captured_auth["url"]).query)
    assert auth_params["access_type"] == ["offline"]
    assert auth_params["prompt"] == ["consent"]
    assert auth_params["code_challenge_method"] == ["S256"]
    assert auth_params["scope"] == [" ".join(YOUTUBE_OAUTH_SCOPES)]

    form = captured_token_req["form"]
    assert form["code"] == ["auth-code-42"]
    assert form["grant_type"] == ["authorization_code"]
    assert form["client_id"] == ["mock-client-id"]
    assert form["client_secret"] == [secret_val]
    assert "code_verifier" in form and len(form["code_verifier"][0]) >= 32

    updated = env_file.read_text(encoding="utf-8")
    assert f'YOUTUBE_REFRESH_TOKEN="{refresh_val}"' in updated
    assert 'ELEVENLABS_API_KEY="el-keep"' in updated


def test_run_oauth_refresh_flow_rejects_state_mismatch_without_modifying_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    original = (
        'YOUTUBE_CLIENT_ID="mock-client-id"\n'
        'YOUTUBE_CLIENT_SECRET="mock-secret"\n'
        'YOUTUBE_REFRESH_TOKEN="original-token"\n'
    )
    env_file.write_text(original, encoding="utf-8")

    def fake_open_browser(auth_url: str) -> bool:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
        redirect_uri = params["redirect_uri"][0]

        def _hit_bad_state() -> None:
            cb_url = f"{redirect_uri}?{urllib.parse.urlencode({'code': 'auth-code', 'state': 'wrong-state'})}"
            with urllib.request.urlopen(cb_url, timeout=5) as resp:
                resp.read()

        threading.Thread(target=_hit_bad_state, daemon=True).start()
        return True

    with pytest.raises(OAuthRefreshError, match="OAuth state validation failed"):
        run_oauth_refresh_flow(
            env_file,
            timeout_seconds=10,
            open_browser_fn=fake_open_browser,
        )

    assert env_file.read_text(encoding="utf-8") == original


def test_run_oauth_refresh_flow_missing_refresh_token_leaves_env_untouched(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    original = (
        'YOUTUBE_CLIENT_ID="mock-client-id"\n'
        'YOUTUBE_CLIENT_SECRET="mock-secret"\n'
        'YOUTUBE_REFRESH_TOKEN="original-token"\n'
    )
    env_file.write_text(original, encoding="utf-8")

    def fake_open_browser(auth_url: str) -> bool:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
        redirect_uri = params["redirect_uri"][0]
        state = params["state"][0]

        def _hit_callback() -> None:
            cb_url = f"{redirect_uri}?{urllib.parse.urlencode({'code': 'auth-code', 'state': state})}"
            with urllib.request.urlopen(cb_url, timeout=5) as resp:
                resp.read()

        threading.Thread(target=_hit_callback, daemon=True).start()
        return True

    def fake_urlopen(req: urllib.request.Request, timeout: int = 30) -> _FakeHTTPResponse:
        return _FakeHTTPResponse({"access_token": "ya29.only-access-token"})

    with pytest.raises(OAuthRefreshError, match="did not return a refresh_token"):
        run_oauth_refresh_flow(
            env_file,
            timeout_seconds=10,
            open_browser_fn=fake_open_browser,
            urlopen_fn=fake_urlopen,
        )

    assert env_file.read_text(encoding="utf-8") == original


def test_cli_main_never_prints_secrets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = tmp_path / ".env.local"
    secret_val = "super-secret-client-value"
    refresh_val = "super-secret-refresh-token"
    env_file.write_text(
        'YOUTUBE_CLIENT_ID="mock-client-id"\n'
        f'YOUTUBE_CLIENT_SECRET="{secret_val}"\n',
        encoding="utf-8",
    )
    real_urlopen = urllib.request.urlopen

    def fake_open_browser(auth_url: str) -> bool:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
        redirect_uri = params["redirect_uri"][0]
        state = params["state"][0]

        def _hit_callback() -> None:
            cb_url = f"{redirect_uri}?{urllib.parse.urlencode({'code': 'code-1', 'state': state})}"
            with real_urlopen(cb_url, timeout=5) as resp:
                resp.read()

        threading.Thread(target=_hit_callback, daemon=True).start()
        return True

    def fake_urlopen(req: urllib.request.Request, timeout: int = 30) -> _FakeHTTPResponse:
        return _FakeHTTPResponse({"access_token": "ya29.fake", "refresh_token": refresh_val})

    with (
        patch("sutradhar.publishing.oauth_refresh.webbrowser.open", side_effect=fake_open_browser),
        patch("sutradhar.publishing.oauth_refresh.urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        rc = refresh_youtube_token.main(["--env-file", str(env_file), "--timeout", "10"])

    captured = capsys.readouterr()
    assert rc == 0
    assert "SUCCESS:" in captured.out
    assert secret_val not in captured.out
    assert secret_val not in captured.err
    assert refresh_val not in captured.out
    assert refresh_val not in captured.err
    assert f'YOUTUBE_REFRESH_TOKEN="{refresh_val}"' in env_file.read_text(encoding="utf-8")


def test_cli_help_exits_zero_without_side_effects() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "refresh_youtube_token.py"), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--env-file" in proc.stdout
    assert "--timeout" in proc.stdout


@pytest.mark.parametrize("bad_token", ["", "   ", "line1\nline2", "line1\rline2", 'has"quote'])
def test_update_refresh_token_rejects_invalid_tokens(tmp_path: Path, bad_token: str) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text('YOUTUBE_CLIENT_ID="id"\n', encoding="utf-8")
    with pytest.raises(OAuthRefreshError):
        update_refresh_token(env_file, 'YOUTUBE_CLIENT_ID="id"\n', bad_token)


def test_run_oauth_refresh_flow_rejects_non_positive_timeout(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text('YOUTUBE_CLIENT_ID="id"\nYOUTUBE_CLIENT_SECRET="sec"\n', encoding="utf-8")
    with pytest.raises(OAuthRefreshError, match="greater than 0"):
        run_oauth_refresh_flow(env_file, timeout_seconds=0)


def test_exchange_authorization_code_sanitizes_http_error() -> None:
    err_body = io.BytesIO(
        json.dumps({"error": "invalid_grant", "error_description": "Token has been expired"}).encode("utf-8")
    )
    http_err = urllib.error.HTTPError(
        TOKEN_ENDPOINT, 400, "Bad Request", hdrs=None, fp=err_body  # type: ignore[arg-type]
    )

    def _raise_http_err(*args: object, **kwargs: object) -> object:
        raise http_err

    with pytest.raises(OAuthRefreshError, match="invalid_grant: Token has been expired"):
        exchange_authorization_code(
            "code", "http://127.0.0.1:1234/", "cid", "csec", "verifier", urlopen_fn=_raise_http_err
        )


def test_load_env_file_uses_shared_parser_for_bom_export_and_comments(tmp_path: Path) -> None:
    assert load_env_file(tmp_path) == {}
    env_file = tmp_path / ".env.local"
    env_file.write_bytes(
        b'\xef\xbb\xbfexport YOUTUBE_CLIENT_ID="cid" # comment\n'
        b"ELEVENLABS_API_KEY='el-key'\n"
    )
    parsed = load_env_file(tmp_path)
    assert parsed == {"YOUTUBE_CLIENT_ID": "cid", "ELEVENLABS_API_KEY": "el-key"}
    assert parse_env_content(env_file.read_text(encoding="utf-8-sig")) == parsed


def test_build_youtube_client_readonly_vs_write_scopes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        'YOUTUBE_CLIENT_ID="cid"\n'
        'YOUTUBE_CLIENT_SECRET="csec"\n'
        'YOUTUBE_REFRESH_TOKEN="rtok"\n',
        encoding="utf-8",
    )

    with (
        patch("google.oauth2.credentials.Credentials") as mock_creds,
        patch("googleapiclient.discovery.build") as mock_build,
    ):
        mock_creds.return_value = MagicMock()
        build_youtube_client(tmp_path, readonly=True)
        assert mock_creds.call_args.kwargs["scopes"] is None
        assert mock_creds.call_args.kwargs["token_uri"] == TOKEN_ENDPOINT
        mock_build.assert_called_once()

        mock_creds.reset_mock()
        mock_build.reset_mock()
        build_youtube_client(tmp_path, readonly=False)
        assert mock_creds.call_args.kwargs["scopes"] == list(YOUTUBE_WRITE_SCOPES)
        assert mock_creds.call_args.kwargs["token_uri"] == TOKEN_ENDPOINT
        mock_build.assert_called_once()

