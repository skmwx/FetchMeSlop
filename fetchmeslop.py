#!/usr/bin/env python3
"""
FetchMeSlop — Generate game UI images via the Replicate API.

Usage:
    python fetchmeslop.py generate --prompt "..." [options]
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

from config import DEFAULT_MODEL, GenerateConfig
from generator import generate_single


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
            "  python fetchmeslop.py generate --prompt \"golden coin icon, pixel art\"\n"
            "  python fetchmeslop.py generate --prompt \"...\" --name coin "
            "--output-dir assets/icons --aspect-ratio 1:1\n"
            "  python fetchmeslop.py generate --prompt \"...\" --dry-run\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # -----------------------------------------------------------------------
    # generate — single image
    # -----------------------------------------------------------------------
    gen = subparsers.add_parser(
        "generate",
        help="Generate a single image from a text prompt.",
        description="Generate one image from a text prompt and save it to disk.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required
    gen.add_argument(
        "--prompt", required=True,
        help="Text prompt sent to the model.",
    )

    # Shared options
    _add_shared_args(gen)

    # generate-specific options
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

    return parser


def _add_shared_args(sub: argparse.ArgumentParser) -> None:
    """Add options that are common to every sub-command."""
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

    # Unreachable today; guards future sub-commands
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
