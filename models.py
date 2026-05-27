"""
models.py — Model registry and input-parameter mapping for FetchMeSlop.

Each entry in KNOWN_MODELS describes how to talk to a specific Replicate
model: which input keys it expects, what it supports, and its native
resolution (used to scale aspect-ratio presets).

To add a new model without editing this file, drop a ``models_extra.yaml``
next to this module.  It must be a YAML mapping of model identifiers to
capability dicts using the same keys as KNOWN_MODELS.

Example ``models_extra.yaml``::

    my-org/my-sdxl-finetune:
      supports_img2img: true
      img2img_input_key: image
      strength_key: prompt_strength
      native_resolution: 1024
      supports_negative_prompt: true
      width_key: width
      height_key: height
      steps_key: num_inference_steps
      guidance_key: guidance_scale
      seed_key: seed
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

KNOWN_MODELS: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # Stability AI — SDXL
    # Supports img2img; marked deprecated on Replicate as of 2025 but
    # still the most widely-documented img2img reference model.
    # ------------------------------------------------------------------
    "stability-ai/sdxl": {
        "supports_img2img": True,
        "img2img_input_key": "image",
        "strength_key": "prompt_strength",
        "native_resolution": 1024,
        "supports_negative_prompt": True,
        "width_key": "width",
        "height_key": "height",
        "steps_key": "num_inference_steps",
        "guidance_key": "guidance_scale",
        "seed_key": "seed",
        "deprecated": True,
    },
    # ------------------------------------------------------------------
    # Stability AI -- Stable Diffusion 3.5 Large (img2img capable)
    # Uses aspect_ratio string ("1:1", "16:9" ...) instead of w/h pixels.
    # ------------------------------------------------------------------
    "stability-ai/stable-diffusion-3.5-large": {
        "supports_img2img": True,
        "img2img_input_key": "image",
        "strength_key": "prompt_strength",
        "native_resolution": 1024,
        "supports_negative_prompt": True,
        "width_key": None,           # model uses aspect_ratio_key instead
        "height_key": None,
        "aspect_ratio_key": "aspect_ratio",   # e.g. "1:1", "16:9"
        "steps_key": "num_inference_steps",
        "guidance_key": "guidance_scale",
        "seed_key": "seed",
    },
    # ------------------------------------------------------------------
    # Black Forest Labs — Flux Schnell  (fast, text2img only)
    # ------------------------------------------------------------------
    "black-forest-labs/flux-schnell": {
        "supports_img2img": False,
        "native_resolution": 1024,
        "supports_negative_prompt": False,
        "width_key": "width",
        "height_key": "height",
        "steps_key": "num_inference_steps",
        "guidance_key": None,
        "seed_key": "seed",
    },
    # ------------------------------------------------------------------
    # Black Forest Labs — Flux Dev  (higher quality, slower)
    # ------------------------------------------------------------------
    "black-forest-labs/flux-dev": {
        "supports_img2img": False,
        "native_resolution": 1024,
        "supports_negative_prompt": False,
        "width_key": "width",
        "height_key": "height",
        "steps_key": "num_inference_steps",
        "guidance_key": "guidance",
        "seed_key": "seed",
    },
    # ------------------------------------------------------------------
    # Black Forest Labs — Flux 2 Pro  (highest quality)
    # ------------------------------------------------------------------
    "black-forest-labs/flux-2-pro": {
        "supports_img2img": False,
        "native_resolution": 1024,
        "supports_negative_prompt": False,
        "width_key": "width",
        "height_key": "height",
        "steps_key": None,    # model manages its own step count
        "guidance_key": None,
        "seed_key": "seed",
    },
}

# Fallback used for models not in KNOWN_MODELS
GENERIC_MODEL: dict[str, Any] = {
    "supports_img2img": False,
    "native_resolution": 1024,
    "supports_negative_prompt": True,
    "width_key": "width",
    "height_key": "height",
    "steps_key": "num_inference_steps",
    "guidance_key": "guidance_scale",
    "seed_key": "seed",
}


# ---------------------------------------------------------------------------
# models_extra.yaml support
# ---------------------------------------------------------------------------

def _load_extra_models() -> None:
    """Merge ``models_extra.yaml`` (if present) into :data:`KNOWN_MODELS`.

    Called once at module import time.  Silently skips if the file does not
    exist.  Emits a warning (to stderr) if pyyaml is missing or the file is
    malformed, but does not abort.
    """
    extra_path = pathlib.Path(__file__).parent / "models_extra.yaml"
    if not extra_path.exists():
        return

    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        print(
            "Warning: models_extra.yaml found but pyyaml is not installed — "
            "extra models will be ignored.\n"
            "  Run: pip install pyyaml",
            file=sys.stderr,
        )
        return

    try:
        with open(extra_path, encoding="utf-8") as fh:
            extra = yaml.safe_load(fh)
    except Exception as exc:  # noqa: BLE001
        print(
            f"Warning: Could not load models_extra.yaml: {exc}",
            file=sys.stderr,
        )
        return

    if not isinstance(extra, dict):
        print(
            "Warning: models_extra.yaml must be a YAML mapping of model-id → capabilities. "
            "Ignoring.",
            file=sys.stderr,
        )
        return

    count = 0
    for model_id, caps in extra.items():
        if not isinstance(caps, dict):
            print(
                f"Warning: Skipping malformed entry '{model_id}' in models_extra.yaml "
                f"(expected a mapping).",
                file=sys.stderr,
            )
            continue
        KNOWN_MODELS[model_id] = caps
        count += 1

    if count:
        print(f"Loaded {count} extra model(s) from models_extra.yaml.", file=sys.stderr)


# Load extra models at import time (silent if file absent)
_load_extra_models()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_model_info(model: str) -> dict[str, Any]:
    """Return the registry entry for *model*, warning if unknown.

    Always returns a dict safe to pass to :func:`build_model_input`.
    """
    if model not in KNOWN_MODELS:
        known = ", ".join(KNOWN_MODELS)
        print(
            f"Warning: Model '{model}' is not in the FetchMeSlop registry.\n"
            f"  Attempting generation with generic parameters.\n"
            f"  Known models: {known}",
            file=sys.stderr,
        )
        return GENERIC_MODEL.copy()

    info = KNOWN_MODELS[model].copy()
    if info.get("deprecated"):
        print(
            f"Warning: Model '{model}' is marked deprecated and may return a 404.",
            file=sys.stderr,
        )
    return info


def build_model_input(
    model_info: dict[str, Any],
    prompt: str,
    width: int,
    height: int,
    negative_prompt: str = "",
    seed: Optional[int] = None,
    num_inference_steps: Optional[int] = None,
    guidance_scale: Optional[float] = None,
) -> dict[str, Any]:
    """Build the Replicate input dict from resolved config + model capabilities.

    Only includes keys the model actually supports; omits keys whose
    registry entry is None or whose caller value is None/empty.
    """
    inp: dict[str, Any] = {"prompt": prompt}

    # Dimensions
    if model_info.get("width_key"):
        inp[model_info["width_key"]] = width
    if model_info.get("height_key"):
        inp[model_info["height_key"]] = height

    # Negative prompt — only if model supports it and caller supplied one
    if negative_prompt and model_info.get("supports_negative_prompt"):
        inp["negative_prompt"] = negative_prompt

    # Seed
    if seed is not None and model_info.get("seed_key"):
        inp[model_info["seed_key"]] = seed

    # Inference steps
    if num_inference_steps is not None and model_info.get("steps_key"):
        inp[model_info["steps_key"]] = num_inference_steps

    # Guidance / CFG scale
    if guidance_scale is not None and model_info.get("guidance_key"):
        inp[model_info["guidance_key"]] = guidance_scale

    return inp
