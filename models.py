"""
models.py — Model registry and input-parameter mapping for FetchMeSlop.

Each entry in KNOWN_MODELS describes how to talk to a specific Replicate
model: which input keys it expects, what it supports, and its native
resolution (used to scale aspect-ratio presets).

To add a new model without editing this file, drop a models_extra.yaml
next to this module (MVP-03+).
"""

from __future__ import annotations

import sys
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

KNOWN_MODELS: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # Stability AI — SDXL
    # NOTE: deprecated on Replicate as of 2025; kept for reference.
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
