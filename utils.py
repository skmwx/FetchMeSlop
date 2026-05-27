"""
utils.py — File naming, folder management, aspect-ratio resolution, and
           image download helpers for FetchMeSlop.
"""

from __future__ import annotations

import pathlib
import sys
import urllib.error
import urllib.request
from typing import Tuple


# ---------------------------------------------------------------------------
# Aspect ratio presets
# ---------------------------------------------------------------------------

ASPECT_RATIO_PRESETS: dict[str, Tuple[int, int]] = {
    "1:1":  (1024, 1024),  # Icons, avatars
    "4:3":  (1024, 768),   # Landscape panels
    "3:4":  (768,  1024),  # Portrait cards
    "16:9": (1024, 576),   # Wide backgrounds
    "9:16": (576,  1024),  # Mobile backgrounds
    "2:1":  (1024, 512),   # Wide banners
}


def resolve_aspect_ratio(aspect_ratio: str) -> Tuple[int, int]:
    """Resolve *aspect_ratio* to a ``(width, height)`` tuple.

    Accepts:
    - A preset shorthand: ``"1:1"``, ``"16:9"``, etc.
    - A custom ``WxH`` string: ``"1280x720"``, ``"800X600"`` (case-insensitive).

    Raises ``ValueError`` for unrecognised input.
    """
    if aspect_ratio in ASPECT_RATIO_PRESETS:
        return ASPECT_RATIO_PRESETS[aspect_ratio]

    # Try WxH custom format (case-insensitive, optional spaces)
    normalised = aspect_ratio.strip().lower().replace(" ", "")
    if "x" in normalised:
        parts = normalised.split("x", maxsplit=1)
        try:
            w, h = int(parts[0]), int(parts[1])
            if w > 0 and h > 0:
                return w, h
        except (ValueError, IndexError):
            pass

    presets = ", ".join(ASPECT_RATIO_PRESETS)
    raise ValueError(
        f"Unrecognised aspect ratio: '{aspect_ratio}'.\n"
        f"  Use a preset ({presets})\n"
        f"  or a custom 'WxH' value (e.g. '1280x720')."
    )


# ---------------------------------------------------------------------------
# Output path helpers — single image
# ---------------------------------------------------------------------------

def build_output_path(output_dir: str, name: str, fmt: str) -> pathlib.Path:
    """Return the full output :class:`~pathlib.Path` for a single image.

    Example::

        build_output_path("assets/icons", "coin-icon", "png")
        # → PosixPath('assets/icons/coin-icon.png')
    """
    return pathlib.Path(output_dir) / f"{name}.{fmt}"


# ---------------------------------------------------------------------------
# Output path helpers — series
# ---------------------------------------------------------------------------

def build_series_output_path(
    output_dir: str,
    name_prefix: str,
    index: int,
    padding: int,
    fmt: str,
) -> pathlib.Path:
    """Return the output :class:`~pathlib.Path` for one frame in a series.

    The filename follows the spec pattern ``{prefix}-{index:0{padding}d}.{fmt}``.

    Example::

        build_series_output_path("assets/ants", "ant-stage", 3, 2, "png")
        # → PosixPath('assets/ants/ant-stage-03.png')

        build_series_output_path("output", "farm-level", 1, 1, "png")
        # → PosixPath('output/farm-level-1.png')
    """
    filename = f"{name_prefix}-{index:0{padding}d}.{fmt}"
    return pathlib.Path(output_dir) / filename


def format_prompt_template(
    template: str,
    n: int,
    total: int,
    name: str,
) -> str:
    """Substitute known tokens in a series prompt template.

    Supported tokens:

    - ``{n}``     — 1-based frame index
    - ``{n0}``    — 0-based frame index
    - ``{total}`` — total number of frames in the series (``count``)
    - ``{name}``  — the ``name_prefix``

    Raises ``KeyError`` for unknown ``{token}`` placeholders.

    Example::

        format_prompt_template("ant stage {n} of {total}", n=3, total=10, name="ant")
        # → 'ant stage 3 of 10'
    """
    return template.format(n=n, n0=n - 1, total=total, name=name)


# ---------------------------------------------------------------------------
# Directory / path guards
# ---------------------------------------------------------------------------

def ensure_output_dir(output_dir: str) -> pathlib.Path:
    """Create *output_dir* (and all parents) if it does not exist.

    Exits with code 4 on permission/OS errors.
    """
    path = pathlib.Path(output_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"Error: Could not create output directory '{output_dir}': {exc}",
            file=sys.stderr,
        )
        sys.exit(4)
    return path


def check_output_path(path: pathlib.Path, overwrite: bool) -> None:
    """Exit with code 4 if *path* already exists and *overwrite* is False."""
    if path.exists() and not overwrite:
        print(
            f"Error: Output file already exists: '{path}'\n"
            f"  Use --overwrite to replace it.",
            file=sys.stderr,
        )
        sys.exit(4)


# ---------------------------------------------------------------------------
# Image download
# ---------------------------------------------------------------------------

def download_image(image_url: str, dest: pathlib.Path) -> None:
    """Download *image_url* and write the bytes to *dest*.

    Exits with code 3 on network errors, code 4 on write errors.
    """
    try:
        urllib.request.urlretrieve(str(image_url), dest)
    except urllib.error.URLError as exc:
        print(f"Error: Could not download image: {exc}", file=sys.stderr)
        sys.exit(3)
    except OSError as exc:
        print(f"Error: Could not write '{dest}': {exc}", file=sys.stderr)
        sys.exit(4)
