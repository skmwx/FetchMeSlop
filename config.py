"""
config.py — Configuration dataclass for FetchMeSlop.

Holds the fully-resolved options for a single generation run.
CLI parsing (in fetchmeslop.py) populates one of these and passes it
to generator.py; nothing in this module touches argparse or the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Default model — flux-schnell is fast, reliable, and actively maintained.
# Override at runtime with --model or $FETCHMESLOP_MODEL.
DEFAULT_MODEL = "black-forest-labs/flux-schnell"


@dataclass
class GenerateConfig:
    """Resolved configuration for a single-image generation run."""

    # ------------------------------------------------------------------ #
    # Required
    # ------------------------------------------------------------------ #
    prompt: str

    # ------------------------------------------------------------------ #
    # Shared options (all commands)
    # ------------------------------------------------------------------ #
    model: str = DEFAULT_MODEL
    format: str = "png"          # png | jpeg | webp
    aspect_ratio: str = "1:1"
    output_dir: str = "./output"
    dry_run: bool = False
    verbose: bool = False
    overwrite: bool = False

    # ------------------------------------------------------------------ #
    # generate-specific options
    # ------------------------------------------------------------------ #
    name: str = "image"
    negative_prompt: str = ""
    seed: Optional[int] = None
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None
