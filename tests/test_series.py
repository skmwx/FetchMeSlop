"""
test_series.py — Unit and integration tests for MVP-03 series generation.

Covers:
- build_series_output_path    (filename construction)
- format_prompt_template      (token substitution)
- SeriesConfig                (dataclass defaults and validation)
- generate_series dry-run     (no Replicate call made)
- generate_series img2img guard (model without img2img support → exit 3)
- generate_series count/start_index validation
- generate_series full mock   (Replicate API fully mocked)
- _load_batch_file            (YAML + JSON loading, defaults merging)
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure project root is on sys.path (handled by conftest.py)
from config import SeriesConfig, DEFAULT_MODEL
from utils import build_series_output_path, format_prompt_template


# ===========================================================================
# build_series_output_path
# ===========================================================================

class TestBuildSeriesOutputPath:
    """Filename follows the spec pattern: {prefix}-{index:0{pad}d}.{ext}"""

    def test_basic_padding_2(self):
        p = build_series_output_path("assets/ants", "ant-stage", 3, 2, "png")
        assert p == pathlib.Path("assets/ants") / "ant-stage-03.png"

    def test_padding_1(self):
        p = build_series_output_path("output", "farm-level", 1, 1, "png")
        assert p == pathlib.Path("output") / "farm-level-1.png"

    def test_padding_3_double_digit(self):
        p = build_series_output_path("output", "item", 42, 3, "jpeg")
        assert p == pathlib.Path("output") / "item-042.jpeg"

    def test_index_10_with_padding_2(self):
        """Index >= 10 should overflow the pad without truncation."""
        p = build_series_output_path("output", "stage", 10, 2, "png")
        assert p == pathlib.Path("output") / "stage-10.png"

    def test_webp_format(self):
        p = build_series_output_path("out", "splash", 1, 2, "webp")
        assert p.suffix == ".webp"

    def test_returns_path_object(self):
        p = build_series_output_path("out", "x", 1, 2, "png")
        assert isinstance(p, pathlib.Path)

    def test_nested_output_dir(self):
        p = build_series_output_path("assets/ants/series", "ant", 5, 2, "png")
        assert p == pathlib.Path("assets/ants/series") / "ant-05.png"

    @pytest.mark.parametrize("prefix, index, pad, expected_name", [
        ("ant-stage", 1,  2, "ant-stage-01.png"),
        ("ant-stage", 10, 2, "ant-stage-10.png"),
        ("farm",      1,  1, "farm-1.png"),
        ("farm",      9,  1, "farm-9.png"),
        ("level",     1,  3, "level-001.png"),
        ("level",     100,3, "level-100.png"),
    ])
    def test_parametrized(self, prefix, index, pad, expected_name):
        p = build_series_output_path("out", prefix, index, pad, "png")
        assert p.name == expected_name


# ===========================================================================
# format_prompt_template
# ===========================================================================

class TestFormatPromptTemplate:
    """All four tokens must substitute correctly."""

    def test_n_token(self):
        assert format_prompt_template("stage {n}", n=3, total=10, name="ant") == "stage 3"

    def test_total_token(self):
        assert format_prompt_template("of {total}", n=1, total=10, name="ant") == "of 10"

    def test_name_token(self):
        assert format_prompt_template("{name} sprite", n=1, total=5, name="ant") == "ant sprite"

    def test_n0_token_is_zero_based(self):
        assert format_prompt_template("index {n0}", n=3, total=10, name="x") == "index 2"
        assert format_prompt_template("index {n0}", n=1, total=10, name="x") == "index 0"

    def test_all_tokens_together(self):
        result = format_prompt_template(
            "{name} stage {n} of {total} (idx {n0})",
            n=5, total=10, name="ant",
        )
        assert result == "ant stage 5 of 10 (idx 4)"

    def test_no_tokens(self):
        """A static template (no tokens) must be returned unchanged."""
        assert format_prompt_template("static prompt", n=1, total=10, name="x") == "static prompt"

    def test_unknown_token_raises_key_error(self):
        with pytest.raises(KeyError):
            format_prompt_template("{unknown_token}", n=1, total=10, name="x")

    def test_repeated_token(self):
        result = format_prompt_template("{n} and again {n}", n=7, total=10, name="x")
        assert result == "7 and again 7"


# ===========================================================================
# SeriesConfig
# ===========================================================================

class TestSeriesConfig:
    """Verify the dataclass has the correct defaults and stores values correctly."""

    def test_required_fields(self):
        cfg = SeriesConfig(prompt_template="test {n}", count=5)
        assert cfg.prompt_template == "test {n}"
        assert cfg.count == 5

    def test_defaults_match_spec(self):
        cfg = SeriesConfig(prompt_template="test", count=3)
        assert cfg.model == DEFAULT_MODEL
        assert cfg.format == "png"
        assert cfg.aspect_ratio == "1:1"
        assert cfg.output_dir == "./output"
        assert cfg.dry_run is False
        assert cfg.verbose is False
        assert cfg.overwrite is False
        assert cfg.name_prefix == "image"
        assert cfg.name_padding == 2
        assert cfg.start_index == 1
        assert cfg.img2img_strength == pytest.approx(0.70)
        assert cfg.negative_prompt == ""
        assert cfg.seed is None
        assert cfg.num_inference_steps is None
        assert cfg.guidance_scale is None

    def test_custom_img2img_strength(self):
        cfg = SeriesConfig(prompt_template="t", count=5, img2img_strength=0.5)
        assert cfg.img2img_strength == pytest.approx(0.5)

    def test_start_index_stored(self):
        cfg = SeriesConfig(prompt_template="t", count=10, start_index=5)
        assert cfg.start_index == 5

    def test_seed_stored(self):
        cfg = SeriesConfig(prompt_template="t", count=3, seed=42)
        assert cfg.seed == 42

    def test_missing_required_raises_type_error(self):
        with pytest.raises(TypeError):
            SeriesConfig()  # type: ignore[call-arg]

    def test_missing_count_raises_type_error(self):
        with pytest.raises(TypeError):
            SeriesConfig(prompt_template="test")  # type: ignore[call-arg]


# ===========================================================================
# generate_series — argument validation (no Replicate calls)
# ===========================================================================

class TestGenerateSeriesValidation:
    """
    generate_series should exit with the appropriate code for bad inputs
    before ever importing or calling the Replicate SDK.
    """

    def _make_config(self, **kwargs) -> SeriesConfig:
        defaults = dict(
            prompt_template="frame {n}",
            count=3,
            model="stability-ai/sdxl",
            output_dir="./output",
        )
        defaults.update(kwargs)
        return SeriesConfig(**defaults)

    def test_count_less_than_1_exits_2(self):
        from generator import generate_series
        cfg = self._make_config(count=0)
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 2

    def test_start_index_less_than_1_exits_2(self):
        from generator import generate_series
        cfg = self._make_config(count=5, start_index=0)
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 2

    def test_start_index_exceeds_count_exits_2(self):
        from generator import generate_series
        cfg = self._make_config(count=5, start_index=6)
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 2

    def test_no_img2img_support_count_gt_1_exits_3(self):
        """flux-schnell doesn't support img2img → code 3 when count > 1."""
        from generator import generate_series
        cfg = self._make_config(count=2, model="black-forest-labs/flux-schnell")
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 3

    def test_no_img2img_support_start_gt_1_exits_3(self):
        """Even count=1 needs img2img if start_index > 1 (reading prev frame)."""
        from generator import generate_series
        cfg = self._make_config(count=5, start_index=2, model="black-forest-labs/flux-schnell")
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 3

    def test_single_frame_no_img2img_needed(self):
        """count=1, start_index=1 with a text2img-only model → OK (dry-run)."""
        from generator import generate_series
        cfg = self._make_config(count=1, model="black-forest-labs/flux-schnell", dry_run=True)
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        # dry-run exits 0, not 3 — no img2img check triggered
        assert exc.value.code == 0


# ===========================================================================
# generate_series — dry-run (no Replicate calls)
# ===========================================================================

class TestGenerateSeriesDryRun:
    """--dry-run must print config and exit 0 without touching Replicate."""

    def test_dry_run_exits_0(self, capsys):
        from generator import generate_series
        cfg = SeriesConfig(
            prompt_template="ant stage {n} of {total}",
            count=3,
            model="stability-ai/sdxl",
            dry_run=True,
        )
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 0

    def test_dry_run_prints_config(self, capsys):
        from generator import generate_series
        cfg = SeriesConfig(
            prompt_template="ant stage {n} of {total}",
            count=5,
            name_prefix="ant",
            model="stability-ai/sdxl",
            dry_run=True,
        )
        with pytest.raises(SystemExit):
            generate_series(cfg)
        out = capsys.readouterr().out
        assert "Dry-run" in out
        assert "ant stage" in out
        assert "5" in out  # count

    def test_dry_run_no_replicate_import(self):
        """Replicate SDK must never be imported during a dry-run."""
        from generator import generate_series
        cfg = SeriesConfig(
            prompt_template="test {n}",
            count=3,
            model="stability-ai/sdxl",
            dry_run=True,
        )
        with patch("generator._import_replicate") as mock_import:
            with pytest.raises(SystemExit):
                generate_series(cfg)
        mock_import.assert_not_called()


# ===========================================================================
# generate_series — resume validation
# ===========================================================================

class TestGenerateSeriesResume:
    """start_index > 1 must verify the previous frame exists."""

    def test_resume_missing_prev_frame_exits_4(self, tmp_path):
        from generator import generate_series
        cfg = SeriesConfig(
            prompt_template="frame {n}",
            count=5,
            start_index=3,          # expects frame-02.png to exist
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="frame",
        )
        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 4

    def test_resume_prev_frame_exists_proceeds(self, tmp_path):
        """When the previous frame exists the function should proceed past
        the resume-guard (here it will fail later due to the mocked API,
        but the exit code will be from a different path)."""
        from generator import generate_series

        # Create the "previous" frame so the guard passes
        prev = tmp_path / "frame-02.png"
        prev.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal PNG header

        cfg = SeriesConfig(
            prompt_template="frame {n}",
            count=5,
            start_index=3,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="frame",
        )

        # Mock Replicate so it returns a fake image URL
        mock_replicate = MagicMock()
        prediction = MagicMock()
        prediction.id = "abc123"
        prediction.status = "succeeded"
        prediction.output = ["https://example.com/out.png"]
        prediction.error = None
        mock_replicate.predictions.create.return_value = prediction

        with patch("generator._import_replicate", return_value=mock_replicate):
            # download_image will fail (no real URL), patch it too
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake_image")
                result = generate_series(cfg)

        # frames 3, 4, 5 should have been generated
        assert len(result) == 3


# ===========================================================================
# generate_series — full mocked run
# ===========================================================================

class TestGenerateSeriesMocked:
    """End-to-end series generation with Replicate and download fully mocked."""

    def _make_mock_replicate(self, output_url="https://example.com/out.png"):
        """Build a mock replicate module whose prediction always succeeds."""
        mock_replicate = MagicMock()
        prediction = MagicMock()
        prediction.id = "testpred"
        prediction.status = "succeeded"
        prediction.output = [output_url]
        prediction.error = None
        mock_replicate.predictions.create.return_value = prediction
        return mock_replicate

    def test_single_frame_produces_one_file(self, tmp_path):
        from generator import generate_series

        cfg = SeriesConfig(
            prompt_template="ant stage {n}",
            count=1,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="ant",
        )

        mock_repl = self._make_mock_replicate()
        with patch("generator._import_replicate", return_value=mock_repl):
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake")
                result = generate_series(cfg)

        assert len(result) == 1
        assert result[0].name == "ant-01.png"

    def test_three_frame_series_all_files_created(self, tmp_path):
        from generator import generate_series

        cfg = SeriesConfig(
            prompt_template="ant stage {n} of {total}",
            count=3,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="ant",
        )

        mock_repl = self._make_mock_replicate()
        with patch("generator._import_replicate", return_value=mock_repl):
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake")
                result = generate_series(cfg)

        assert len(result) == 3
        assert [p.name for p in result] == ["ant-01.png", "ant-02.png", "ant-03.png"]

    def test_first_frame_is_text2img_subsequent_use_img2img(self, tmp_path):
        """
        Frame 1: predictions.create called WITHOUT an 'image' key in input.
        Frames 2+: predictions.create called WITH an 'image' key (open file).
        """
        from generator import generate_series

        cfg = SeriesConfig(
            prompt_template="frame {n}",
            count=3,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="frame",
            img2img_strength=0.65,
        )

        captured_inputs: list[dict] = []
        mock_repl = MagicMock()

        def fake_create(model, input):
            # Snapshot which keys were present (file objects → just mark True)
            snap = {k: (v if not hasattr(v, "read") else "<file>") for k, v in input.items()}
            captured_inputs.append(snap)
            pred = MagicMock()
            pred.id = f"pred{len(captured_inputs)}"
            pred.status = "succeeded"
            pred.output = [f"https://example.com/frame{len(captured_inputs)}.png"]
            pred.error = None
            return pred

        mock_repl.predictions.create.side_effect = fake_create

        with patch("generator._import_replicate", return_value=mock_repl):
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake")
                generate_series(cfg)

        assert len(captured_inputs) == 3

        # Frame 1 — text2img: no 'image' key
        assert "image" not in captured_inputs[0], (
            "Frame 1 should be text2img (no 'image' key in input)"
        )

        # Frames 2 & 3 — img2img: must have 'image' and 'prompt_strength' keys
        for frame_idx, inp in enumerate(captured_inputs[1:], start=2):
            assert "image" in inp, f"Frame {frame_idx} should include 'image' key"
            assert "prompt_strength" in inp, f"Frame {frame_idx} should include 'prompt_strength'"
            assert inp["prompt_strength"] == pytest.approx(0.65)

    def test_prompt_template_interpolated_correctly(self, tmp_path):
        """The prompt passed to Replicate must contain the resolved template."""
        from generator import generate_series

        cfg = SeriesConfig(
            prompt_template="stage {n} of {total} — {name}",
            count=2,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="ant",
        )

        received_prompts: list[str] = []
        mock_repl = MagicMock()

        def fake_create(model, input):
            received_prompts.append(input.get("prompt", ""))
            pred = MagicMock()
            pred.id = "p"
            pred.status = "succeeded"
            pred.output = ["https://example.com/x.png"]
            pred.error = None
            return pred

        mock_repl.predictions.create.side_effect = fake_create

        with patch("generator._import_replicate", return_value=mock_repl):
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake")
                generate_series(cfg)

        assert received_prompts[0] == "stage 1 of 2 — ant"
        assert received_prompts[1] == "stage 2 of 2 — ant"

    def test_overwrite_false_existing_file_exits_4(self, tmp_path):
        """If a target file already exists and --overwrite is False, exit 4."""
        from generator import generate_series

        # Pre-create frame 1
        existing = tmp_path / "ant-01.png"
        existing.write_bytes(b"existing")

        cfg = SeriesConfig(
            prompt_template="frame {n}",
            count=3,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="ant",
            overwrite=False,
        )

        with pytest.raises(SystemExit) as exc:
            generate_series(cfg)
        assert exc.value.code == 4

    def test_seed_offset_per_frame(self, tmp_path):
        """Each frame's seed should be base_seed + (frame_index - 1)."""
        from generator import generate_series

        cfg = SeriesConfig(
            prompt_template="frame {n}",
            count=3,
            model="stability-ai/sdxl",
            output_dir=str(tmp_path),
            name_prefix="f",
            seed=100,
        )

        received_seeds: list[int] = []
        mock_repl = MagicMock()

        def fake_create(model, input):
            received_seeds.append(input.get("seed"))
            pred = MagicMock()
            pred.id = "p"
            pred.status = "succeeded"
            pred.output = ["https://example.com/x.png"]
            pred.error = None
            return pred

        mock_repl.predictions.create.side_effect = fake_create

        with patch("generator._import_replicate", return_value=mock_repl):
            with patch("generator.download_image") as mock_dl:
                mock_dl.side_effect = lambda url, dest: dest.write_bytes(b"fake")
                generate_series(cfg)

        # Frame 1 → seed 100 (100 + 0), Frame 2 → 101, Frame 3 → 102
        assert received_seeds == [100, 101, 102]


# ===========================================================================
# _load_batch_file (inline helper tests via fetchmeslop imports)
# ===========================================================================

class TestLoadBatchFile:
    """Batch config loader — YAML, JSON, defaults merging, error cases."""

    def _write_yaml(self, tmp_path: pathlib.Path, content: str) -> pathlib.Path:
        p = tmp_path / "batch.yaml"
        p.write_text(content, encoding="utf-8")
        return p

    def _write_json(self, tmp_path: pathlib.Path, data: dict) -> pathlib.Path:
        p = tmp_path / "batch.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_yaml_jobs_loaded(self, tmp_path):
        from fetchmeslop import _load_batch_file
        cfg_path = self._write_yaml(tmp_path, """
jobs:
  - command: generate
    prompt: "coin icon"
    name: coin
""")
        jobs = _load_batch_file(str(cfg_path))
        assert len(jobs) == 1
        assert jobs[0]["command"] == "generate"
        assert jobs[0]["prompt"] == "coin icon"

    def test_json_jobs_loaded(self, tmp_path):
        from fetchmeslop import _load_batch_file
        cfg_path = self._write_json(tmp_path, {
            "jobs": [{"command": "generate", "prompt": "sword", "name": "sword"}]
        })
        jobs = _load_batch_file(str(cfg_path))
        assert len(jobs) == 1
        assert jobs[0]["prompt"] == "sword"

    def test_defaults_merged_into_jobs(self, tmp_path):
        from fetchmeslop import _load_batch_file
        cfg_path = self._write_yaml(tmp_path, """
defaults:
  model: stability-ai/sdxl
  format: jpeg
  output_dir: assets/

jobs:
  - command: generate
    prompt: "coin"
    name: coin
  - command: generate
    prompt: "sword"
    name: sword
    format: png  # override default
""")
        jobs = _load_batch_file(str(cfg_path))
        assert len(jobs) == 2
        # Both inherit model and output_dir from defaults
        assert jobs[0]["model"] == "stability-ai/sdxl"
        assert jobs[0]["output_dir"] == "assets/"
        assert jobs[0]["format"] == "jpeg"
        # Second job overrides format
        assert jobs[1]["format"] == "png"
        assert jobs[1]["output_dir"] == "assets/"

    def test_missing_file_exits_2(self, tmp_path):
        from fetchmeslop import _load_batch_file
        with pytest.raises(SystemExit) as exc:
            _load_batch_file(str(tmp_path / "nonexistent.yaml"))
        assert exc.value.code == 2

    def test_unsupported_extension_exits_2(self, tmp_path):
        from fetchmeslop import _load_batch_file
        p = tmp_path / "batch.toml"
        p.write_text("[jobs]", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _load_batch_file(str(p))
        assert exc.value.code == 2

    def test_empty_jobs_returns_empty_list(self, tmp_path):
        from fetchmeslop import _load_batch_file
        cfg_path = self._write_yaml(tmp_path, "jobs: []\n")
        jobs = _load_batch_file(str(cfg_path))
        assert jobs == []

    def test_multiple_job_types(self, tmp_path):
        from fetchmeslop import _load_batch_file
        cfg_path = self._write_yaml(tmp_path, """
jobs:
  - command: generate
    prompt: "coin"
    name: coin
  - command: series
    prompt_template: "ant stage {n}"
    count: 5
    name_prefix: ant
""")
        jobs = _load_batch_file(str(cfg_path))
        assert len(jobs) == 2
        assert jobs[0]["command"] == "generate"
        assert jobs[1]["command"] == "series"
        assert jobs[1]["count"] == 5


# ===========================================================================
# _job_to_generate_config / _job_to_series_config
# ===========================================================================

class TestJobToConfig:
    """Conversion from batch job dicts to typed config objects."""

    def test_generate_config_required_field(self):
        from fetchmeslop import _job_to_generate_config
        cfg = _job_to_generate_config(
            {"command": "generate", "prompt": "a coin", "name": "coin"},
            job_idx=1,
        )
        assert cfg.prompt == "a coin"
        assert cfg.name == "coin"

    def test_generate_config_defaults(self):
        from fetchmeslop import _job_to_generate_config
        cfg = _job_to_generate_config({"command": "generate", "prompt": "x"}, job_idx=1)
        assert cfg.model == DEFAULT_MODEL
        assert cfg.format == "png"
        assert cfg.aspect_ratio == "1:1"

    def test_generate_config_missing_prompt_exits_2(self):
        from fetchmeslop import _job_to_generate_config
        with pytest.raises(SystemExit) as exc:
            _job_to_generate_config({"command": "generate"}, job_idx=1)
        assert exc.value.code == 2

    def test_series_config_required_fields(self):
        from fetchmeslop import _job_to_series_config
        cfg = _job_to_series_config(
            {"command": "series", "prompt_template": "frame {n}", "count": 10},
            job_idx=1,
        )
        assert cfg.prompt_template == "frame {n}"
        assert cfg.count == 10

    def test_series_config_defaults(self):
        from fetchmeslop import _job_to_series_config
        cfg = _job_to_series_config(
            {"command": "series", "prompt_template": "t", "count": 5},
            job_idx=1,
        )
        assert cfg.name_prefix == "image"
        assert cfg.name_padding == 2
        assert cfg.start_index == 1
        assert cfg.img2img_strength == pytest.approx(0.70)

    def test_series_config_missing_prompt_template_exits_2(self):
        from fetchmeslop import _job_to_series_config
        with pytest.raises(SystemExit) as exc:
            _job_to_series_config({"command": "series", "count": 5}, job_idx=1)
        assert exc.value.code == 2

    def test_series_config_missing_count_exits_2(self):
        from fetchmeslop import _job_to_series_config
        with pytest.raises(SystemExit) as exc:
            _job_to_series_config(
                {"command": "series", "prompt_template": "t"},
                job_idx=1,
            )
        assert exc.value.code == 2
