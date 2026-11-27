"""Visual storyboard compiler and thumbnail builder package for Sutradhar v2."""

from sutradhar.visual.storyboard_composer import (
    CAPTION_SAFE_BOTTOM_MAX,
    CompiledComposition,
    CompositionError,
    GROUND_TOLERANCE_PX,
    compose_storyboard,
    load_asset_registry,
    parse_manifest_js,
    validate_storyboard_grounding,
    verify_plan_audio_parity,
)
from sutradhar.visual.thumbnail_builder import (
    SHORTS_2X3_CROP_BOX,
    ThumbnailBuildError,
    ThumbnailBuildResult,
    build_thumbnail,
    save_shorts_2x3_crop,
)

__all__ = [
    "CAPTION_SAFE_BOTTOM_MAX",
    "CompiledComposition",
    "CompositionError",
    "GROUND_TOLERANCE_PX",
    "SHORTS_2X3_CROP_BOX",
    "ThumbnailBuildError",
    "ThumbnailBuildResult",
    "build_thumbnail",
    "compose_storyboard",
    "load_asset_registry",
    "parse_manifest_js",
    "save_shorts_2x3_crop",
    "validate_storyboard_grounding",
    "verify_plan_audio_parity",
]
