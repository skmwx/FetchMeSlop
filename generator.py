"""
generator.py -- Core generation logic for FetchMeSlop.

This module is the only place that imports the ``replicate`` SDK,
so SDK-related errors are isolated here.

Public API:
    generate_single(config: GenerateConfig) -> pathlib.Path
    generate_series(config: SeriesConfig)   -> list[pathlib.Path]
"""

from __future__ import annotations

import pathlib
import sys
import time

from config import GenerateConfig, SeriesConfig
from models import get_model_info, build_model_input
from utils import (
    resolve_aspect_ratio,
    build_output_path,
    build_series_output_path,
    format_prompt_template,
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
            "\nReplicate authentication error -- your REPLICATE_API_TOKEN may be invalid.\n"
            f"  Details: {msg}",
            file=sys.stderr,
        )
    else:
        print(f"\n{context}: {msg}", file=sys.stderr)
    sys.exit(3)


def _extract_image_url(output) -> str:
    """Coerce Replicate output to a plain URL string.

    Replicate models return different types:
    - ``list[str | FileOutput]`` -- most models
    - A single ``str | FileOutput`` -- some models (e.g. flux-2-pro)
    ``FileOutput`` objects expose their URL via ``.url`` or ``str()``.
    """
    if isinstance(output, list):
        output = output[0]
    if hasattr(output, "url"):
        return str(output.url)
    return str(output)


def _run_prediction(
    replicate,
    model: str,
    model_input: dict,
    verbose: bool,
) -> tuple[str, str]:
    """Submit one prediction to Replicate and wait for completion.

    Returns:
        ``(image_url, prediction_url)``

    Exits with code 3 on any unrecoverable API error.

    .. note::
        If ``model_input`` contains an open file object (e.g. for img2img),
        the caller is responsible for keeping it open until this function
        returns.
    """
    if verbose:
        print("  Submitting prediction to Replicate...")

    # Retry up to 5 times on 429 rate-limit responses, with exponential backoff.
    _max_retries = 5
    for _attempt in range(_max_retries):
        try:
            prediction = replicate.predictions.create(
                model=model,
                input=model_input,
            )
            break  # success -- exit retry loop
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc) and _attempt < _max_retries - 1:
                _delay = 15 * (2 ** _attempt)  # 15s, 30s, 60s, 120s, ...
                print(
                    f"\n  Rate limited (429). "
                    f"Waiting {_delay}s before retry "
                    f"({_attempt + 1}/{_max_retries - 1})...",
                    flush=True,
                )
                time.sleep(_delay)
            else:
                _handle_api_error("Failed to create prediction", exc)

    prediction_url = f"https://replicate.com/p/{prediction.id}"
    if verbose:
        print(f"  Prediction URL : {prediction_url}")

    print("  Waiting for result...", end="", flush=True)
    try:
        prediction.wait()
    except Exception as exc:  # noqa: BLE001
        print()  # newline after "Waiting..."
        _handle_api_error("Prediction failed while waiting", exc)
    print(" done.")

    if prediction.status == "failed":
        print(
            "\nReplicate reported a prediction failure.\n"
            f"  Error          : {prediction.error}\n"
            f"  Prediction URL : {prediction_url}",
            file=sys.stderr,
        )
        sys.exit(3)

    if not prediction.output:
        print("Error: Replicate returned no output.", file=sys.stderr)
        sys.exit(3)

    image_url = _extract_image_url(prediction.output)

    if verbose:
        print(f"  Image URL      : {image_url}")

    return image_url, prediction_url


def _print_dry_run(
    config: GenerateConfig,
    width: int,
    height: int,
    output_path: pathlib.Path,
    model_info: dict,
) -> None:
    """Print the resolved configuration for ``--dry-run`` mode (single image)."""
    print("Dry-run -- resolved configuration")
    print("-" * 40)
    print(f"  Model               : {config.model}")
    print(f"  Prompt              : {config.prompt}")
    if config.negative_prompt:
        print(f"  Negative prompt     : {config.negative_prompt}")
    print(f"  Dimensions          : {width}x{height}  (--aspect-ratio {config.aspect_ratio})")
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


def _print_series_dry_run(
    config: SeriesConfig,
    width: int,
    height: int,
    model_info: dict,
) -> None:
    """Print the resolved configuration for ``--dry-run`` mode (series)."""
    num_to_generate = config.count - config.start_index + 1

    print("Dry-run -- resolved series configuration")
    print("-" * 40)
    print(f"  Model               : {config.model}")
    print(f"  Prompt template     : {config.prompt_template}")
    print(f"  Total series count  : {config.count}")
    print(f"  Start index         : {config.start_index}")
    print(f"  Frames to generate  : {num_to_generate}")
    if config.negative_prompt:
        print(f"  Negative prompt     : {config.negative_prompt}")
    print(f"  Dimensions          : {width}x{height}  (--aspect-ratio {config.aspect_ratio})")
    print(f"  Format              : {config.format}")
    print(f"  Output dir          : {config.output_dir}")
    print(f"  Name prefix         : {config.name_prefix}")
    print(f"  Name padding        : {config.name_padding}")
    print(f"  img2img strength    : {config.img2img_strength}")
    if config.seed is not None:
        print(f"  Seed (frame 1)      : {config.seed}")
    print(f"  Supports img2img    : {model_info.get('supports_img2img', False)}")
    print()

    # Show a few example filenames + resolved prompts
    preview_count = min(3, num_to_generate)
    print("Example filenames:")
    for i in range(config.start_index, config.start_index + preview_count):
        path = build_series_output_path(
            config.output_dir, config.name_prefix, i, config.name_padding, config.format
        )
        try:
            prompt = format_prompt_template(
                config.prompt_template, n=i, total=config.count, name=config.name_prefix
            )
        except KeyError:
            prompt = config.prompt_template
        print(f"  {path.name}  --  {prompt!r}")
    if num_to_generate > 3:
        last_path = build_series_output_path(
            config.output_dir, config.name_prefix, config.count, config.name_padding, config.format
        )
        print(f"  ...")
        print(f"  {last_path.name}  ({num_to_generate} frames total)")

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
    # 1. Resolve aspect ratio -> pixel dimensions
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

    # Handle models that take "aspect_ratio" string instead of width/height pixels
    if model_info.get("aspect_ratio_key"):
        model_input[model_info["aspect_ratio_key"]] = config.aspect_ratio

    if config.verbose:
        print(f"  Dimensions  : {width}x{height}")
        print(f"  Model input : {model_input}")

    # 7. Submit prediction and wait
    replicate = _import_replicate()

    image_url, prediction_url = _run_prediction(
        replicate, config.model, model_input, config.verbose
    )

    # 8. Download image and print prediction URL
    download_image(image_url, output_path)
    print(f"  Prediction URL : {prediction_url}")

    return output_path


def generate_series(config: SeriesConfig) -> list[pathlib.Path]:
    """Generate a numbered series of images using img2img chaining.

    Frame 1 is produced via text2img.  Each subsequent frame is produced via
    img2img using the previous frame's output as the ``image`` input, with
    ``img2img_strength`` controlling how much the content may diverge.

    Returns a list of :class:`~pathlib.Path` objects for every file written
    during *this* call (previously existing frames are not included).

    Exits (via ``sys.exit``) on any unrecoverable error.
    """
    # 1. Resolve aspect ratio
    try:
        width, height = resolve_aspect_ratio(config.aspect_ratio)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    # 2. Validate count / start_index
    if config.count < 1:
        print("Error: --count must be at least 1.", file=sys.stderr)
        sys.exit(2)
    if config.start_index < 1:
        print("Error: --start-index must be at least 1.", file=sys.stderr)
        sys.exit(2)
    if config.start_index > config.count:
        print(
            f"Error: --start-index ({config.start_index}) cannot exceed "
            f"--count ({config.count}).",
            file=sys.stderr,
        )
        sys.exit(2)

    # 3. Look up model capabilities
    model_info = get_model_info(config.model)

    # 4. Validate img2img support.
    #    We need img2img when generating any frame past the very first frame of
    #    the series, i.e. when start_index > 1 OR when we'll generate > 1 frame.
    num_to_generate = config.count - config.start_index + 1
    needs_img2img = (config.start_index > 1) or (num_to_generate > 1)

    if needs_img2img and not model_info.get("supports_img2img"):
        print(
            f"Error: Model '{config.model}' does not support img2img, "
            "which is required for series generation with more than one frame.\n"
            "\n"
            "  Choose a model that supports img2img, for example:\n"
            "    --model stability-ai/sdxl\n"
            "\n"
            "  Or add a custom img2img-capable model to models_extra.yaml.",
            file=sys.stderr,
        )
        sys.exit(3)

    # 5. Dry-run: print config and exit
    if config.dry_run:
        _print_series_dry_run(config, width, height, model_info)
        sys.exit(0)

    # 6. Ensure output directory exists
    ensure_output_dir(config.output_dir)

    # 7. When resuming (start_index > 1), verify the previous frame exists
    prev_image_path: pathlib.Path | None = None
    if config.start_index > 1:
        prev_path = build_series_output_path(
            config.output_dir,
            config.name_prefix,
            config.start_index - 1,
            config.name_padding,
            config.format,
        )
        if not prev_path.exists():
            print(
                f"Error: Cannot resume at --start-index {config.start_index}.\n"
                f"  Expected previous frame at '{prev_path}' but it does not exist.\n"
                f"  Ensure the series has been run up to frame "
                f"{config.start_index - 1} before resuming.",
                file=sys.stderr,
            )
            sys.exit(4)
        prev_image_path = prev_path

    # 8. Import Replicate SDK
    replicate = _import_replicate()

    # 9. Generate each frame
    output_paths: list[pathlib.Path] = []

    for i in range(config.start_index, config.count + 1):
        output_path = build_series_output_path(
            config.output_dir, config.name_prefix, i, config.name_padding, config.format
        )
        check_output_path(output_path, config.overwrite)

        # Resolve prompt for this frame
        try:
            prompt = format_prompt_template(
                config.prompt_template,
                n=i,
                total=config.count,
                name=config.name_prefix,
            )
        except KeyError as exc:
            print(
                f"Error: Unknown token {exc} in --prompt-template.\n"
                "  Supported tokens: {n}, {n0}, {total}, {name}",
                file=sys.stderr,
            )
            sys.exit(2)

        frame_num = i - config.start_index + 1
        print(f"\n[{frame_num}/{num_to_generate}] Frame {i}/{config.count}: {output_path.name}")
        if config.verbose:
            print(f"  Prompt : {prompt!r}")
            print(f"  Size   : {width}x{height}")

        # Per-frame seed: offset by frame index so each frame is reproducible
        # but distinct even with the same base seed.
        frame_seed: int | None = None
        if config.seed is not None:
            frame_seed = config.seed + (i - 1)

        # Build base model input (text2img parameters)
        model_input = build_model_input(
            model_info=model_info,
            prompt=prompt,
            width=width,
            height=height,
            negative_prompt=config.negative_prompt,
            seed=frame_seed,
            num_inference_steps=config.num_inference_steps,
            guidance_scale=config.guidance_scale,
        )

        # Handle models that take "aspect_ratio" string instead of width/height
        if model_info.get("aspect_ratio_key"):
            model_input[model_info["aspect_ratio_key"]] = config.aspect_ratio

        # Inject img2img parameters for all frames after the first
        if prev_image_path is not None:
            img2img_key = model_info.get("img2img_input_key", "image")
            # strength_key may be None for models without a strength parameter
            # (e.g. flux-2-flex uses reference images with no strength control)
            strength_key = model_info.get("strength_key", "prompt_strength")
            # img2img_list_input=True means the input key expects a list of images
            # rather than a single image (e.g. flux-2-flex's "input_images" field)
            img2img_list_input = model_info.get("img2img_list_input", False)

            if config.verbose:
                strength_info = (
                    f", strength={config.img2img_strength}" if strength_key else ""
                )
                print(
                    f"  img2img base : {prev_image_path.name}"
                    f"  ({strength_info.lstrip(', ')})"
                )

            # Open the previous frame and submit while the file handle is live.
            with open(prev_image_path, "rb") as img_file:
                if img2img_list_input:
                    model_input[img2img_key] = [img_file]
                else:
                    model_input[img2img_key] = img_file
                # Only inject strength if the model exposes a strength parameter
                if strength_key:
                    model_input[strength_key] = config.img2img_strength
                image_url, prediction_url = _run_prediction(
                    replicate, config.model, model_input, config.verbose
                )
        else:
            # First frame of the series -- plain text2img
            image_url, prediction_url = _run_prediction(
                replicate, config.model, model_input, config.verbose
            )

        print(f"  Prediction URL : {prediction_url}")
        download_image(image_url, output_path)
        output_paths.append(output_path)

        # This frame becomes the base for the next frame
        prev_image_path = output_path

    return output_paths
