"""
test_utils.py — Unit tests for utils.py.

Covers:
- resolve_aspect_ratio  (presets + custom WxH + error cases)
- build_output_path     (path construction)
- check_output_path     (overwrite guard)
- ASPECT_RATIO_PRESETS  (completeness)
"""

import pathlib
import tempfile

import pytest

from utils import (
    ASPECT_RATIO_PRESETS,
    build_output_path,
    check_output_path,
    resolve_aspect_ratio,
)


# ---------------------------------------------------------------------------
# resolve_aspect_ratio
# ---------------------------------------------------------------------------

class TestResolveAspectRatioPresets:
    """All six spec-defined presets must map to their documented dimensions."""

    @pytest.mark.parametrize("preset, expected", [
        ("1:1",  (1024, 1024)),
        ("4:3",  (1024, 768)),
        ("3:4",  (768,  1024)),
        ("16:9", (1024, 576)),
        ("9:16", (576,  1024)),
        ("2:1",  (1024, 512)),
    ])
    def test_preset(self, preset, expected):
        assert resolve_aspect_ratio(preset) == expected


class TestResolveAspectRatioCustom:
    """Custom WxH strings must be parsed to integer tuples."""

    def test_standard_custom(self):
        assert resolve_aspect_ratio("1280x720") == (1280, 720)

    def test_square_custom(self):
        assert resolve_aspect_ratio("512x512") == (512, 512)

    def test_legacy_vga(self):
        assert resolve_aspect_ratio("800x600") == (800, 600)

    def test_uppercase_x(self):
        """Parser must be case-insensitive."""
        assert resolve_aspect_ratio("1920X1080") == (1920, 1080)

    def test_leading_trailing_spaces(self):
        assert resolve_aspect_ratio("  640x480  ") == (640, 480)


class TestResolveAspectRatioErrors:
    """Invalid inputs must raise ValueError, not crash silently."""

    def test_totally_invalid(self):
        with pytest.raises(ValueError):
            resolve_aspect_ratio("invalid")

    def test_ratio_colon_not_supported_for_arbitrary(self):
        """'5:3' is not a preset and not WxH — must raise."""
        with pytest.raises(ValueError):
            resolve_aspect_ratio("5:3")

    def test_zero_width(self):
        with pytest.raises(ValueError):
            resolve_aspect_ratio("0x480")

    def test_zero_height(self):
        with pytest.raises(ValueError):
            resolve_aspect_ratio("640x0")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            resolve_aspect_ratio("")


class TestAspectRatioPresets:
    """Smoke-test the ASPECT_RATIO_PRESETS constant itself."""

    def test_six_presets_defined(self):
        """Spec defines 6 presets (custom WxH is not a preset entry)."""
        assert len(ASPECT_RATIO_PRESETS) == 6

    def test_all_values_are_positive_int_pairs(self):
        for key, (w, h) in ASPECT_RATIO_PRESETS.items():
            assert isinstance(w, int) and w > 0, f"Bad width for {key}"
            assert isinstance(h, int) and h > 0, f"Bad height for {key}"


# ---------------------------------------------------------------------------
# build_output_path
# ---------------------------------------------------------------------------

class TestBuildOutputPath:
    """Output paths must follow the {output_dir}/{name}.{fmt} pattern."""

    def test_basic_png(self):
        result = build_output_path("output", "coin-icon", "png")
        assert result == pathlib.Path("output") / "coin-icon.png"

    def test_nested_dir(self):
        result = build_output_path("assets/icons", "coin", "jpeg")
        assert result == pathlib.Path("assets/icons") / "coin.jpeg"

    def test_webp_format(self):
        result = build_output_path("./output", "splash", "webp")
        assert result == pathlib.Path("./output") / "splash.webp"

    def test_returns_path_object(self):
        result = build_output_path("output", "test", "png")
        assert isinstance(result, pathlib.Path)

    def test_name_with_hyphens(self):
        result = build_output_path("output", "ant-stage-01", "png")
        assert result.name == "ant-stage-01.png"


# ---------------------------------------------------------------------------
# check_output_path
# ---------------------------------------------------------------------------

class TestCheckOutputPath:
    """check_output_path must exit(4) when the file exists and overwrite=False."""

    def test_nonexistent_file_passes(self):
        """Should not raise for a path that does not exist."""
        p = pathlib.Path("/nonexistent/path/that/does/not/exist.png")
        # Must not raise or sys.exit
        check_output_path(p, overwrite=False)

    def test_existing_file_without_overwrite_exits(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            existing = pathlib.Path(f.name)
        try:
            with pytest.raises(SystemExit) as exc_info:
                check_output_path(existing, overwrite=False)
            assert exc_info.value.code == 4
        finally:
            existing.unlink(missing_ok=True)

    def test_existing_file_with_overwrite_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            existing = pathlib.Path(f.name)
        try:
            # Must NOT call sys.exit when overwrite=True
            check_output_path(existing, overwrite=True)
        finally:
            existing.unlink(missing_ok=True)
