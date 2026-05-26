"""
generator.py — Core generation logic for FetchMeSlop.

This module is the only place that imports the ``replicate`` SDK,
so SDK-related errors are isolated here.
"""

from __future__ import annotations

import sys
import pathlib

from config import GenerateConfig
from models import get_model_info, build_model_input
from utils import (
    resolve_aspect_ratio,
    build_output_path,
    ensure_output_dir,
    check_output_path,
    download_image,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _import_replicate():
    """Import the replicate SDK or exit with a clear error."""
    try:
        import replicate  # noqa: PLC0415
        return replicate
    except ImportError:
        print(
            "Error: 'replicate' package is not installed.\n"
            "Run:  pip install replicate",
            file=sys.stderr,
        )
        sys.exit(1)


def _handle_api_error(context: str, exc: Exception) -> None:
    """Print a friendly error for Replicate API failures and exit with code 3."""
    msg = str(exc)
    if any(tag in msg for tag in ("401", "authentication", "unauthorized", "Unauthorized")):
        print(
            f"\nReplicate authentication error — your REPLICATE_API_TOKEN may be invalid.\n"
            f"  Details: {msg}",
            file=sys.stderr,
        )
    else:
        print(f"\n{context}: {msg}", file=sys.stderr)
    sys.exit(3)


def _extract_image_url(output) -> str:
    """Coerce Replicate output to a plain URL string.

    Replicate models return different types:
    - ``list[str | FileOutput]`` — most models
    - A single ``str | FileOutput`` — some models (e.g. flux-2-pro)
    ``FileOutput`` objects expose their URL via ``.url`` or ``str()``.
    """
    if isinstance(output, list):
        output = output[0]
    if hasattr(output, "url"):
        return str(output.url)
    return str(output)


def _print_dry_run(
    config: GenerateConfig,
    width: int,
    height: int,
    output_path: pathlib.Path,
    model_info: dict,
) -> None:
    """Print the resolved configuration for ``--dry-run`` mode."""
    print("Dry-run — resolved configuration")
    print("─" * 40)
    print(f"  Model               : {config.model}")
    print(f"  Prompt              : {config.prompt}")
    if config.negative_prompt:
        print(f"  Negative prompt     : {config.negative_prompt}")
    print(f"  Dimensions          : {width}×{height}  (--aspect-ratio {config.aspect_ratio})")
    print(f"  Format              : {config.format}")
    print(f"  Output              : {output_path}")
    if config.seed is not None:
        print(f"  Seed                : {config.seed}")
    if config.num_inference_steps is not None:
        print(f"  Inference steps     : {config.num_inference_steps}")
    if config.guidance_scale is not None:
        print(f"  Guidance scale      : {config.guidance_scale}")
    print(f"  Supports img2img    : {model_info.get('supports_img2img', False)}")
    print(f"  Supports neg prompt : {model_info.get('supports_negative_prompt', False)}")
    print()
    print("No API call made (--dry-run).")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_single(config: GenerateConfig) -> pathlib.Path:
    """Generate one image from *config* and return its saved :class:`~pathlib.Path`.

    Side-effects:
    - Creates ``config.output_dir`` if it does not exist.
    - Writes a file at the resolved output path.
    - Exits (via ``sys.exit``) on any unrecoverable error.
    """
    # 1. Resolve aspect ratio → pixel dimensions
    try:
        width, height = resolve_aspect_ratio(config.aspect_ratio)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    # 2. Look up model capabilities
    model_info = get_model_info(config.model)

    # 3. Build the output path (needed for dry-run display too)
    output_path = build_output_path(config.output_dir, config.name, config.format)

    # 4. Dry-run: show config and exit without touching Replicate
    if config.dry_run:
        _print_dry_run(config, width, height, output_path, model_info)
        sys.exit(0)

    # 5. Ensure output directory exists and path is clear
    ensure_output_dir(config.output_dir)
    check_output_path(output_path, config.overwrite)

    # 6. Build Replicate input dict
    model_input = build_model_input(
        model_info=model_info,
        prompt=config.prompt,
        width=width,
        height=height,
        negative_prompt=config.negative_prompt,
        seed=config.seed,
        num_inference_steps=config.num_inference_steps,
        guidance_scale=config.guidance_scale,
    )

    if config.verbose:
        print(f"  Dimensions  : {width}×{height}")
        print(f"  Model input : {model_input}")

    # 7. Submit prediction
    replicate = _import_replicate()

    if config.verbose:
        print("Submitting prediction to Replicate…")

    try:
        prediction = replicate.predictions.create(
            model=config.model,
            input=model_input,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_api_error("Failed to create prediction", exc)

    prediction_url = f"https://replicate.com/p/{prediction.id}"
    if config.verbose:
        print(f"  Prediction URL : {prediction_url}")

    # 8. Wait for completion
    print("Waiting for result…", end="", flush=True)
    try:
        prediction.wait()
    except Exception as exc:  # noqa: BLE001
        print()  # newline after "Waiting…"
        _handle_api_error("Prediction failed while waiting", exc)
    print(" done.")

    if prediction.status == "failed":
        print(
            f"\nReplicate reported a prediction failure.\n"
            f"  Error          : {prediction.error}\n"
            f"  Prediction URL : {prediction_url}",
            file=sys.stderr,
        )
        sys.exit(3)

    # 9. Extract image URL and download
    if not prediction.output:
        print("Error: Replicate returned no output.", file=sys.stderr)
        sys.exit(3)

    image_url = _extract_image_url(prediction.output)

    if config.verbose:
        print(f"  Image URL      : {image_url}")

    download_image(image_url, output_path)

    # 10. Always print the prediction URL (spec requirement)
    print(f"  Prediction URL : {prediction_url}")

    return output_path
