"""
test_config.py — Unit tests for config.py (GenerateConfig dataclass).
"""

import pytest
from config import GenerateConfig, DEFAULT_MODEL


class TestGenerateConfigDefaults:
    """Verify the out-of-the-box defaults match the spec."""

    def test_default_model(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.model == DEFAULT_MODEL

    def test_default_format(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.format == "png"

    def test_default_aspect_ratio(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.aspect_ratio == "1:1"

    def test_default_output_dir(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.output_dir == "./output"

    def test_default_name(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.name == "image"

    def test_default_negative_prompt_is_empty_string(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.negative_prompt == ""

    def test_optional_ints_default_to_none(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.seed is None
        assert cfg.num_inference_steps is None

    def test_optional_float_defaults_to_none(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.guidance_scale is None

    def test_flags_default_to_false(self):
        cfg = GenerateConfig(prompt="test")
        assert cfg.dry_run is False
        assert cfg.verbose is False
        assert cfg.overwrite is False


class TestGenerateConfigCustomValues:
    """Verify that non-default values are stored correctly."""

    def test_prompt_stored(self):
        cfg = GenerateConfig(prompt="golden coin icon, pixel art")
        assert cfg.prompt == "golden coin icon, pixel art"

    def test_custom_model(self):
        cfg = GenerateConfig(prompt="x", model="black-forest-labs/flux-2-pro")
        assert cfg.model == "black-forest-labs/flux-2-pro"

    def test_custom_format(self):
        cfg = GenerateConfig(prompt="x", format="jpeg")
        assert cfg.format == "jpeg"

    def test_custom_aspect_ratio(self):
        cfg = GenerateConfig(prompt="x", aspect_ratio="16:9")
        assert cfg.aspect_ratio == "16:9"

    def test_custom_output_dir(self):
        cfg = GenerateConfig(prompt="x", output_dir="assets/icons")
        assert cfg.output_dir == "assets/icons"

    def test_custom_name(self):
        cfg = GenerateConfig(prompt="x", name="coin-icon")
        assert cfg.name == "coin-icon"

    def test_seed_stored(self):
        cfg = GenerateConfig(prompt="x", seed=42)
        assert cfg.seed == 42

    def test_num_inference_steps_stored(self):
        cfg = GenerateConfig(prompt="x", num_inference_steps=30)
        assert cfg.num_inference_steps == 30

    def test_guidance_scale_stored(self):
        cfg = GenerateConfig(prompt="x", guidance_scale=7.5)
        assert cfg.guidance_scale == pytest.approx(7.5)

    def test_dry_run_flag(self):
        cfg = GenerateConfig(prompt="x", dry_run=True)
        assert cfg.dry_run is True

    def test_verbose_flag(self):
        cfg = GenerateConfig(prompt="x", verbose=True)
        assert cfg.verbose is True

    def test_overwrite_flag(self):
        cfg = GenerateConfig(prompt="x", overwrite=True)
        assert cfg.overwrite is True

    def test_prompt_is_required(self):
        """GenerateConfig must raise TypeError when prompt is omitted."""
        with pytest.raises(TypeError):
            GenerateConfig()  # type: ignore[call-arg]
