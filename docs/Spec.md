# FetchMeSlop — Image Generation Tool Specification

## Overview

**FetchMeSlop** is a Python CLI tool for generating game UI images via the Replicate API. It supports single-image generation, background/large-asset generation, and coherent series of thematically related images using img2img chaining. The tool is designed for programmatic use by AI coding agents (Claude Code, Codex, etc.) while remaining fully operable by a human developer from the terminal.

---

## Goals

- Generate individual small UI icons (currency, arrows, buttons).
- Generate large assets such as screen backgrounds or splash art.
- Generate logically connected series of images (evolution stages, upgrade tiers, rarity variants) using img2img to preserve visual consistency across the set.
- Be model-agnostic: any Replicate-hosted image model can be selected at runtime.
- Produce predictable, structured output filenames and folder layouts for easy integration into a game asset pipeline.

---

## Non-Goals (out of scope for MVP)

- Image editing / post-processing (cropping, compositing, palette shifting).
- Hosting or serving images.
- Direct integration with any specific game engine.
- Batch parallelism beyond sequential series generation.

---

## Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Image model provider | [Replicate](https://replicate.com) via `replicate` Python SDK |
| Series consistency | img2img: the first generated image is fed as `image` input to subsequent predictions |
| Configuration | CLI flags (primary) + optional JSON/YAML config file |
| Output | PNG files (default); JPEG, WebP configurable |
| Credentials | `REPLICATE_API_TOKEN` environment variable |

---

## Architecture

```
fetchmeslop/
├── fetchmeslop.py        # CLI entry point
├── generator.py          # Core generation logic (single + series)
├── config.py             # Config dataclass + loader
├── models.py             # Model registry / preset catalogue
├── utils.py              # File naming, folder creation, helpers
├── requirements.txt
└── README.md
```

The tool is invoked as:

```
python fetchmeslop.py [command] [options]
```

or, once installed:

```
fetchmeslop [command] [options]
```

---

## Commands

### `generate` — single image

Generates one image from a text prompt.

```
fetchmeslop generate \
  --prompt "a golden coin icon, pixel art, game UI, transparent background" \
  --model stability-ai/sdxl \
  --format png \
  --aspect-ratio 1:1 \
  --output-dir assets/icons \
  --name coin-icon
```

Output: `assets/icons/coin-icon.png`

### `series` — connected set of images

Generates N images, each seeded from the previous one via img2img to maintain visual coherence.

```
fetchmeslop series \
  --prompt-template "an ant at evolution stage {n} of 10, game sprite, side view" \
  --count 10 \
  --model stability-ai/sdxl \
  --img2img-strength 0.65 \
  --format png \
  --aspect-ratio 1:1 \
  --output-dir assets/ants \
  --name-prefix ant-stage \
  --name-padding 2
```

Output: `assets/ants/ant-stage-01.png` … `assets/ants/ant-stage-10.png`

The `{n}` token in `--prompt-template` is replaced with the current index (1-based). Additional tokens:
- `{n0}` — zero-based index
- `{total}` — total count
- `{name}` — the name prefix

### `batch` (MVP-03 stretch) — multiple named series from a config file

Reads a JSON/YAML config describing multiple generate/series jobs and runs them sequentially.

```
fetchmeslop batch --config batch.yaml
```

---

## CLI Options Reference

### Shared options (all commands)

| Flag | Type | Default | Description |
|---|---|---|---|
| `--model` | string | `stability-ai/sdxl` | Replicate model identifier (`owner/model` or `owner/model:version`) |
| `--format` | `png\|jpeg\|webp` | `png` | Output image format |
| `--aspect-ratio` | string | `1:1` | Aspect ratio shorthand; see table below |
| `--output-dir` | path | `./output` | Destination folder; created if absent |
| `--dry-run` | flag | false | Print resolved config and exit without calling Replicate |
| `--verbose` | flag | false | Print Replicate prediction URLs and progress |

### `generate`-only options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--prompt` | string | required | Text prompt sent to the model |
| `--name` | string | `image` | Output filename stem (without extension) |
| `--negative-prompt` | string | `""` | Negative prompt (if model supports it) |
| `--seed` | int | random | RNG seed for reproducibility |
| `--num-inference-steps` | int | model default | Denoising steps |
| `--guidance-scale` | float | model default | CFG scale |

### `series`-only options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--prompt-template` | string | required | Prompt with `{n}`, `{total}` tokens |
| `--count` | int | required | Number of images to generate |
| `--name-prefix` | string | `image` | Common prefix for all filenames |
| `--name-padding` | int | `2` | Zero-pad width for the numeric suffix |
| `--start-index` | int | `1` | Index of the first image |
| `--img2img-strength` | float | `0.70` | How much the next image diverges from the previous (0.0–1.0) |
| `--seed` | int | random | Seed for the first image; subsequent images inherit it + offset |
| `--negative-prompt` | string | `""` | Applied to every frame |

---

## Aspect Ratio Presets

| Shorthand | Width × Height | Use case |
|---|---|---|
| `1:1` | 1024×1024 | Icons, avatars |
| `4:3` | 1024×768 | Landscape panels |
| `3:4` | 768×1024 | Portrait cards |
| `16:9` | 1024×576 | Wide backgrounds |
| `9:16` | 576×1024 | Mobile backgrounds |
| `2:1` | 1024×512 | Wide banners |
| `custom WxH` | user-defined | Any dimensions |

Model-specific width/height are derived from the aspect ratio and the model's native resolution. If the model does not support the requested size natively, the closest valid dimensions are chosen and the user is warned.

---

## File Naming Convention

Filenames follow the pattern:

```
{name-prefix}-{index:0{padding}d}.{format}
```

Examples with `--name-prefix ant-stage --name-padding 2 --count 10`:

```
ant-stage-01.png
ant-stage-02.png
...
ant-stage-10.png
```

Examples with `--name-prefix farm-level --name-padding 1 --count 3`:

```
farm-level-1.png
farm-level-2.png
farm-level-3.png
```

Single images use `--name` directly: `coin-icon.png`.

If a file with the target name already exists, the tool exits with an error by default. `--overwrite` allows replacement.

---

## img2img Series Logic

```
┌──────────────────────────────────────────┐
│  Frame 1: text2img                       │
│  prompt = template.format(n=1)           │
│  → saved as {prefix}-01.{ext}            │
└───────────────┬──────────────────────────┘
                │ output image
                ▼
┌──────────────────────────────────────────┐
│  Frame 2: img2img                        │
│  image  = Frame 1 output                 │
│  prompt = template.format(n=2)           │
│  strength = --img2img-strength           │
│  → saved as {prefix}-02.{ext}            │
└───────────────┬──────────────────────────┘
                │ output image
                ▼
              ...
```

Each frame's output becomes the `image` input for the next frame. The prompt evolves via the template. This ensures the visual style (colour palette, line weight, perspective) stays coherent across all stages while the content shifts according to the prompt progression.

**Strength guidance:**

| Value | Effect |
|---|---|
| 0.4–0.5 | Very similar frames (subtle upgrades) |
| 0.6–0.75 | Noticeable changes while preserving style (recommended) |
| 0.8–0.95 | Large divergence per step |

---

## Configuration File (optional)

For `batch` or reusable presets, a YAML config is supported:

```yaml
# fetchmeslop.yaml
defaults:
  model: stability-ai/sdxl
  format: png
  output_dir: assets/

jobs:
  - command: generate
    name: coin-icon
    prompt: "golden coin, pixel art, game UI, transparent background"
    aspect_ratio: "1:1"
    output_dir: assets/icons/

  - command: series
    name_prefix: ant-stage
    count: 10
    prompt_template: "ant at evolution stage {n} of {total}, game sprite, detailed"
    aspect_ratio: "1:1"
    img2img_strength: 0.65
    output_dir: assets/ants/

  - command: series
    name_prefix: farm-level
    count: 3
    prompt_template: "farm building upgrade level {n}, isometric game art"
    aspect_ratio: "4:3"
    img2img_strength: 0.55
    output_dir: assets/buildings/
```

CLI flags override config-file values.

---

## Model Registry

`models.py` ships with a small catalogue of known Replicate models and their parameter mappings:

```python
KNOWN_MODELS = {
    "stability-ai/sdxl": {
        "supports_img2img": True,
        "img2img_input_key": "image",
        "strength_key": "prompt_strength",
        "native_resolution": 1024,
        "supports_negative_prompt": True,
    },
    "black-forest-labs/flux-schnell": {
        "supports_img2img": False,
        "native_resolution": 1024,
        "supports_negative_prompt": False,
    },
    # ... extend as needed
}
```

Unknown models fall back to a generic parameter set and emit a warning. Users can extend the registry via a local `models_extra.yaml` file.

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error (see stderr) |
| 2 | Invalid arguments |
| 3 | Replicate API error |
| 4 | File write error (e.g., path exists, permission denied) |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `REPLICATE_API_TOKEN` | Yes | Replicate account API key |
| `FETCHMESLOP_OUTPUT_DIR` | No | Default output directory override |
| `FETCHMESLOP_MODEL` | No | Default model override |

---

## Error Handling

- API errors: print the Replicate error message, log the prediction URL if available, exit with code 3.
- Missing output directory: create it automatically (recursive).
- File already exists: exit with code 4 unless `--overwrite` is set.
- Model not in registry: warn and attempt generation with generic parameters.
- img2img not supported by selected model: exit with a clear error message recommending a compatible model.

---

## MVP Definitions

### MVP-01 — API Connection & File Write Smoke Test

**Goal:** Prove that the Replicate API call works and that a file can be written to disk.

**Scope:**
- Single hardcoded prompt, model, and output path (no CLI flags required).
- Calls Replicate, downloads the result, writes it to `output/test.png`.
- Prints success message with the file path and prediction URL.
- No config, no series, no naming options.

**Acceptance criteria:**
1. Running `python fetchmeslop.py` (no args) produces `output/test.png`.
2. The file is a valid PNG image.
3. The prediction URL is printed to stdout.
4. A missing or invalid `REPLICATE_API_TOKEN` produces a clear error, not a stack trace.

**Deliverables:** `fetchmeslop.py` (single file), `requirements.txt`, `README.md` with setup steps.

---

### MVP-02 — Flexible Single-Image Generation

**Goal:** Full CLI for generating one image with configurable model, prompt, format, aspect ratio, naming, and output path.

**Scope:**
- `generate` command with all flags listed in the CLI Options Reference above.
- Aspect ratio presets resolved to width/height.
- Structured output filename from `--name` and `--output-dir`.
- `--dry-run` mode.
- `--verbose` mode.
- Model registry (`models.py`) with at least SDXL and Flux Schnell entries.
- Basic error handling with exit codes.

**Acceptance criteria:**
1. `fetchmeslop generate --prompt "..." --name coin --output-dir assets/icons` writes `assets/icons/coin.png`.
2. `--aspect-ratio 16:9` correctly maps to model-appropriate dimensions.
3. `--dry-run` prints the resolved config and exits 0 without calling Replicate.
4. Unsupported model emits a warning but still attempts the call.
5. All exit codes behave as documented.

**Deliverables:** Full package structure, unit tests for `config.py` and `utils.py`.

---

### MVP-03 — Series Generation (img2img Chaining)

**Goal:** Generate a numbered series of visually coherent images using img2img.

**Scope:**
- `series` command with all series-specific flags.
- img2img chaining: output of frame N is passed as `image` input to frame N+1.
- Prompt template with `{n}`, `{total}`, `{name}` tokens.
- Configurable `--img2img-strength`.
- File naming with `--name-prefix` and `--name-padding`.
- Optional YAML config file support and `batch` command.
- `--start-index` to resume an interrupted series.

**Acceptance criteria:**
1. `fetchmeslop series --prompt-template "ant stage {n} of {total}" --count 10 --name-prefix ant --output-dir assets/ants` writes `ant-01.png` through `ant-10.png`.
2. Each file after the first is generated via img2img from the prior file.
3. `--img2img-strength 0.5` produces visually smoother progressions than `0.9` (verified manually).
4. Selecting a model that does not support img2img exits with code 3 and a helpful message.
5. `fetchmeslop batch --config batch.yaml` runs all jobs in order.
6. Interrupting mid-series and re-running with `--start-index` resumes correctly without overwriting completed files (unless `--overwrite` is set).

**Deliverables:** Full feature-complete tool, integration tests against Replicate sandbox/mock, updated README with series examples.

---

## Future Considerations (post-MVP)

- **Parallel generation:** fan-out multiple independent prompts concurrently.
- **ControlNet / depth guidance:** feed a reference silhouette for stronger shape consistency.
- **Inpainting mode:** mask-based targeted edits on existing assets.
- **Asset manifest:** emit a JSON manifest listing every generated file with metadata (prompt, model, seed, dimensions).
- **GUI mode:** simple Tkinter/Gradio interface for human use.
- **Claude MCP server:** expose `generate` and `series` as MCP tools for direct agent invocation without subprocess overhead.
