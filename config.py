"""
config.py — Configuration dataclasses for FetchMeSlop.

Holds the fully-resolved options for single-image and series generation runs.
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


@dataclass
class SeriesConfig:
    """Resolved configuration for a series generation run (img2img chaining).

    ``count`` is the *total* series length (used for ``{total}`` template
    substitution and to determine the final frame index).  The number of
    frames actually generated equals ``count - start_index + 1``.

    Example — resume from frame 5 of a 10-frame series::

        SeriesConfig(
            prompt_template="ant stage {n} of {total}",
            count=10,
            start_index=5,
            name_prefix="ant",
        )
        # generates ant-05.png … ant-10.png (6 frames)
        # reads ant-04.png as the img2img base for ant-05.png
    """

    # ------------------------------------------------------------------ #
    # Required
    # ------------------------------------------------------------------ #
    prompt_template: str
    count: int

    # ------------------------------------------------------------------ #
    # Shared options (all commands)
    # ------------------------------------------------------------------ #
    model: str = DEFAULT_MODEL
    format: str = "png"
    aspect_ratio: str = "1:1"
    output_dir: str = "./output"
    dry_run: bool = False
    verbose: bool = False
    overwrite: bool = False

    # ------------------------------------------------------------------ #
    # Series-specific options
    # ------------------------------------------------------------------ #
    name_prefix: str = "image"
    name_padding: int = 2
    start_index: int = 1
    img2img_strength: float = 0.70
    negative_prompt: str = ""
    seed: Optional[int] = None
    num_inference_steps: Optional[int] = None
    guidance_scale: Optional[float] = None
