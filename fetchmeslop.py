#!/usr/bin/env python3
"""
FetchMeSlop -- Generate game UI images via the Replicate API.

Usage:
    python fetchmeslop.py generate --prompt "..." [options]
    python fetchmeslop.py series  --prompt-template "..." --count N [options]
    python fetchmeslop.py batch   --config batch.yaml
    python fetchmeslop.py --help

Exit codes:
    0  Success
    1  Missing / invalid REPLICATE_API_TOKEN, or import error
    2  Invalid arguments
    3  Replicate API error
    4  File write error (path exists, permission denied, etc.)
"""

from __future__ import annotations

import argparse
import os
import sys

from config import DEFAULT_MODEL, GenerateConfig, SeriesConfig
from generator import generate_single, generate_series


# ---------------------------------------------------------------------------
# Token check
# ---------------------------------------------------------------------------

def _check_token() -> None:
    """Exit with code 1 if REPLICATE_API_TOKEN is absent."""
    token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not token:
        print(
            "Error: REPLICATE_API_TOKEN environment variable is not set.\n"
            "\n"
            "Get your token at https://replicate.com/account/api-tokens\n"
            "then set it before running:\n"
            "\n"
            "  Windows PowerShell:\n"
            "    $env:REPLICATE_API_TOKEN = 'r8_...'\n"
            "\n"
            "  macOS / Linux:\n"
            "    export REPLICATE_API_TOKEN='r8_...'",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetchmeslop",
        description="Generate game UI images via the Replicate API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python fetchmeslop.py generate \\\n"
            "      --prompt \"golden coin icon, pixel art\" --name coin\n"
            "\n"
            "  python fetchmeslop.py series \\\n"
            "      --prompt-template \"ant stage {n} of {total}, sprite\" \\\n"
            "      --count 10 --name-prefix ant --model stability-ai/sdxl\n"
            "\n"
            "  python fetchmeslop.py batch --config batch.yaml\n"
            "\n"
            "  python fetchmeslop.py generate --prompt \"...\" --dry-run\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # -----------------------------------------------------------------------
    # generate -- single image
    # -----------------------------------------------------------------------
    gen = subparsers.add_parser(
        "generate",
        help="Generate a single image from a text prompt.",
        description="Generate one image from a text prompt and save it to disk.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    gen.add_argument(
        "--prompt", required=True,
        help="Text prompt sent to the model.",
    )
    _add_shared_args(gen)
    gen.add_argument(
        "--name", default="image", metavar="STEM",
        help="Output filename stem (without extension).",
    )
    gen.add_argument(
        "--negative-prompt", default="", metavar="TEXT",
        help="Negative prompt (ignored if the model does not support it).",
    )
    gen.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for reproducibility.",
    )
    gen.add_argument(
        "--num-inference-steps", type=int, default=None, metavar="N",
        help="Denoising steps (uses the model default if omitted).",
    )
    gen.add_argument(
        "--guidance-scale", type=float, default=None, metavar="F",
        help="CFG guidance scale (uses the model default if omitted).",
    )
    gen.add_argument(
        "--overwrite", action="store_true",
        help="Replace the output file if it already exists.",
    )

    # -----------------------------------------------------------------------
    # series -- img2img chained set
    # -----------------------------------------------------------------------
    ser = subparsers.add_parser(
        "series",
        help="Generate a numbered series of images via img2img chaining.",
        description=(
            "Generate N images in sequence. The first frame is produced via "
            "text2img; each subsequent frame takes the previous image as its "
            "img2img base, keeping style coherent while the prompt evolves.\n"
            "\n"
            "Template tokens: {n} (1-based index), {n0} (0-based), "
            "{total} (series length), {name} (name-prefix)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ser.add_argument(
        "--prompt-template", required=True, metavar="TEMPLATE",
        help=(
            "Prompt with {n}, {total}, {name} tokens. "
            "Example: \"ant at evolution stage {n} of {total}, game sprite\""
        ),
    )
    ser.add_argument(
        "--count", type=int, required=True, metavar="N",
        help="Total number of images in the series (determines {total} and the last file index).",
    )
    _add_shared_args(ser)
    ser.add_argument(
        "--name-prefix", default="image", metavar="PREFIX",
        help="Common filename prefix for all frames.",
    )
    ser.add_argument(
        "--name-padding", type=int, default=2, metavar="N",
        help="Zero-pad width for the numeric suffix (2 -> ant-01.png ... ant-10.png).",
    )
    ser.add_argument(
        "--start-index", type=int, default=1, metavar="N",
        help=(
            "Index of the first frame to generate. Set > 1 to resume an "
            "interrupted series; the tool will read frame start-index-1 as "
            "the img2img base. The number of frames generated equals "
            "count - start-index + 1."
        ),
    )
    ser.add_argument(
        "--img2img-strength", type=float, default=0.70, metavar="F",
        help=(
            "How much each frame may diverge from the previous (0.0-1.0). "
            "0.5 = subtle changes; 0.7 = noticeable but coherent (default); "
            "0.9 = large divergence."
        ),
    )
    ser.add_argument(
        "--negative-prompt", default="", metavar="TEXT",
        help="Negative prompt applied to every frame.",
    )
    ser.add_argument(
        "--seed", type=int, default=None,
        help="Seed for the first frame; subsequent frames use seed + frame_index.",
    )
    ser.add_argument(
        "--num-inference-steps", type=int, default=None, metavar="N",
        help="Denoising steps (uses the model default if omitted).",
    )
    ser.add_argument(
        "--guidance-scale", type=float, default=None, metavar="F",
        help="CFG guidance scale (uses the model default if omitted).",
    )
    ser.add_argument(
        "--overwrite", action="store_true",
        help="Replace output files if they already exist.",
    )

    # -----------------------------------------------------------------------
    # batch -- multiple jobs from a config file
    # -----------------------------------------------------------------------
    bat = subparsers.add_parser(
        "batch",
        help="Run multiple generate/series jobs from a YAML or JSON config file.",
        description=(
            "Read a YAML or JSON config file describing multiple generate/series "
            "jobs and run them sequentially.\n"
            "\n"
            "Config format:\n"
            "  defaults:          # optional, merged into every job\n"
            "    model: ...\n"
            "    output_dir: ...\n"
            "  jobs:\n"
            "    - command: generate\n"
            "      prompt: \"...\"\n"
            "      name: coin\n"
            "    - command: series\n"
            "      prompt_template: \"stage {n} of {total}\"\n"
            "      count: 5\n"
            "      name_prefix: stage\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bat.add_argument(
        "--config", required=True, metavar="FILE",
        help="Path to a YAML (.yaml/.yml) or JSON (.json) batch config file.",
    )

    return parser


def _add_shared_args(sub: argparse.ArgumentParser) -> None:
    """Add options common to both ``generate`` and ``series``."""
    sub.add_argument(
        "--model", default=DEFAULT_MODEL, metavar="OWNER/MODEL",
        help="Replicate model identifier.",
    )
    sub.add_argument(
        "--format", choices=["png", "jpeg", "webp"], default="png",
        help="Output image format.",
    )
    sub.add_argument(
        "--aspect-ratio", default="1:1", metavar="RATIO",
        help=(
            "Aspect ratio preset (1:1, 4:3, 3:4, 16:9, 9:16, 2:1) "
            "or custom WxH (e.g. 1280x720)."
        ),
    )
    sub.add_argument(
        "--output-dir", default="./output", metavar="DIR",
        help="Destination folder; created automatically if absent.",
    )
    sub.add_argument(
        "--dry-run", action="store_true",
        help="Print the resolved config and exit without calling Replicate.",
    )
    sub.add_argument(
        "--verbose", action="store_true",
        help="Print Replicate prediction URLs and extra progress info.",
    )


# ---------------------------------------------------------------------------
# Batch config loading
# ---------------------------------------------------------------------------

def _load_batch_file(config_path: str) -> list[dict]:
    """Load a YAML or JSON batch config and return the merged jobs list.

    Each job dict has ``defaults`` values pre-merged in; the ``command`` key
    is guaranteed to be present.
    """
    import pathlib

    path = pathlib.Path(config_path)
    if not path.exists():
        print(
            f"Error: Batch config file not found: '{config_path}'",
            file=sys.stderr,
        )
        sys.exit(2)

    suffix = path.suffix.lower()

    if suffix == ".json":
        import json
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"Error: Invalid JSON in '{config_path}': {exc}", file=sys.stderr)
            sys.exit(2)

    elif suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            print(
                "Error: pyyaml is required for YAML batch configs.\n"
                "  Run: pip install pyyaml",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"Error: Invalid YAML in '{config_path}': {exc}", file=sys.stderr)
            sys.exit(2)

    else:
        print(
            f"Error: Unsupported config file extension '{suffix}'. "
            "Use .yaml, .yml, or .json.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not isinstance(data, dict):
        print(
            "Error: Batch config must be a YAML/JSON object with 'jobs' key.",
            file=sys.stderr,
        )
        sys.exit(2)

    defaults: dict = data.get("defaults") or {}
    raw_jobs: list = data.get("jobs") or []

    if not raw_jobs:
        print(f"Warning: No jobs found in '{config_path}'.")
        return []

    merged_jobs: list[dict] = []
    for idx, job in enumerate(raw_jobs, 1):
        if not isinstance(job, dict):
            print(
                f"Error: Job {idx} in '{config_path}' is not a mapping.",
                file=sys.stderr,
            )
            sys.exit(2)
        merged_jobs.append({**defaults, **job})

    return merged_jobs


def _job_to_generate_config(job: dict, job_idx: int) -> GenerateConfig:
    """Convert a merged batch job dict to a :class:`~config.GenerateConfig`."""
    prompt = job.get("prompt")
    if not prompt:
        print(
            f"Error: Batch job {job_idx} (generate) is missing required field 'prompt'.",
            file=sys.stderr,
        )
        sys.exit(2)

    return GenerateConfig(
        prompt=str(prompt),
        model=str(job.get("model", DEFAULT_MODEL)),
        format=str(job.get("format", "png")),
        aspect_ratio=str(job.get("aspect_ratio", "1:1")),
        output_dir=str(job.get("output_dir", "./output")),
        dry_run=bool(job.get("dry_run", False)),
        verbose=bool(job.get("verbose", False)),
        overwrite=bool(job.get("overwrite", False)),
        name=str(job.get("name", "image")),
        negative_prompt=str(job.get("negative_prompt", "")),
        seed=job.get("seed"),
        num_inference_steps=job.get("num_inference_steps"),
        guidance_scale=job.get("guidance_scale"),
    )


def _job_to_series_config(job: dict, job_idx: int) -> SeriesConfig:
    """Convert a merged batch job dict to a :class:`~config.SeriesConfig`."""
    prompt_template = job.get("prompt_template")
    if not prompt_template:
        print(
            f"Error: Batch job {job_idx} (series) is missing required field "
            "'prompt_template'.",
            file=sys.stderr,
        )
        sys.exit(2)

    count = job.get("count")
    if count is None:
        print(
            f"Error: Batch job {job_idx} (series) is missing required field 'count'.",
            file=sys.stderr,
        )
        sys.exit(2)

    return SeriesConfig(
        prompt_template=str(prompt_template),
        count=int(count),
        model=str(job.get("model", DEFAULT_MODEL)),
        format=str(job.get("format", "png")),
        aspect_ratio=str(job.get("aspect_ratio", "1:1")),
        output_dir=str(job.get("output_dir", "./output")),
        dry_run=bool(job.get("dry_run", False)),
        verbose=bool(job.get("verbose", False)),
        overwrite=bool(job.get("overwrite", False)),
        name_prefix=str(job.get("name_prefix", "image")),
        name_padding=int(job.get("name_padding", 2)),
        start_index=int(job.get("start_index", 1)),
        img2img_strength=float(job.get("img2img_strength", 0.70)),
        negative_prompt=str(job.get("negative_prompt", "")),
        seed=job.get("seed"),
        num_inference_steps=job.get("num_inference_steps"),
        guidance_scale=job.get("guidance_scale"),
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_generate(args: argparse.Namespace) -> int:
    _check_token()

    config = GenerateConfig(
        prompt=args.prompt,
        model=args.model,
        format=args.format,
        aspect_ratio=args.aspect_ratio,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
        name=args.name,
        negative_prompt=args.negative_prompt,
        seed=args.seed,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        overwrite=args.overwrite,
    )

    if not config.dry_run:
        print(f"Generating '{config.name}.{config.format}' with {config.model}")

    output_path = generate_single(config)

    if not config.dry_run:
        print(f"\nSaved: {output_path.resolve()}")

    return 0


def _cmd_series(args: argparse.Namespace) -> int:
    _check_token()

    config = SeriesConfig(
        prompt_template=args.prompt_template,
        count=args.count,
        model=args.model,
        format=args.format,
        aspect_ratio=args.aspect_ratio,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
        name_prefix=args.name_prefix,
        name_padding=args.name_padding,
        start_index=args.start_index,
        img2img_strength=args.img2img_strength,
        negative_prompt=args.negative_prompt,
        seed=args.seed,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        overwrite=args.overwrite,
    )

    num_to_generate = config.count - config.start_index + 1

    if not config.dry_run:
        resume_note = (
            f" (resuming from frame {config.start_index})" if config.start_index > 1 else ""
        )
        print(
            f"Generating series '{config.name_prefix}' -- "
            f"{num_to_generate} frame(s){resume_note} with {config.model}"
        )

    output_paths = generate_series(config)

    if not config.dry_run:
        print(f"\nSeries complete -- {len(output_paths)} image(s) saved to '{config.output_dir}'.")

    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    jobs = _load_batch_file(args.config)

    if not jobs:
        print("No jobs to run.")
        return 0

    print(f"Running {len(jobs)} job(s) from '{args.config}'...")

    for idx, job in enumerate(jobs, 1):
        command = job.get("command")
        if command not in ("generate", "series"):
            print(
                f"Error: Job {idx} has unknown command '{command}'. "
                "Must be 'generate' or 'series'.",
                file=sys.stderr,
            )
            sys.exit(2)

        print(f"\n{'-' * 50}")
        print(f"[{idx}/{len(jobs)}] {command.upper()}")
        print(f"{'-' * 50}")

        if command == "generate":
            cfg = _job_to_generate_config(job, idx)
            _check_token()
            if not cfg.dry_run:
                print(f"Generating '{cfg.name}.{cfg.format}' with {cfg.model}")
            output_path = generate_single(cfg)
            if not cfg.dry_run:
                print(f"Saved: {output_path.resolve()}")

        else:  # series
            cfg = _job_to_series_config(job, idx)
            _check_token()
            num_to_generate = cfg.count - cfg.start_index + 1
            if not cfg.dry_run:
                print(
                    f"Generating series '{cfg.name_prefix}' -- "
                    f"{num_to_generate} frame(s) with {cfg.model}"
                )
            output_paths = generate_series(cfg)
            if not cfg.dry_run:
                print(f"Saved {len(output_paths)} image(s) to '{cfg.output_dir}'.")

    print(f"\n{'=' * 50}")
    print(f"Batch complete -- {len(jobs)} job(s) finished.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "generate":
        return _cmd_generate(args)

    if args.command == "series":
        return _cmd_series(args)

    if args.command == "batch":
        return _cmd_batch(args)

    # Unreachable; guards future sub-commands
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
