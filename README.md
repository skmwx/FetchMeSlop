# FetchMeSlop

A Python CLI tool for generating game UI images via the [Replicate](https://replicate.com) API.

Supports:
- **Single-image generation** — one image from a text prompt with full model/format/size control.
- **Series generation** — N images chained via img2img so style stays coherent as the prompt evolves.
- **Batch mode** — run multiple generate/series jobs from a single YAML or JSON config file.

---

## Requirements

- Python 3.11 or newer
- A [Replicate](https://replicate.com) account with an API token

---

## Setup

### 1. Clone / download the project

```powershell
git clone <repo-url>
cd FetchMeSlop
```

### 2. Create and activate a virtual environment (recommended)

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Set your Replicate API token

Get your token at <https://replicate.com/account/api-tokens>.

**Windows (PowerShell) — current session only:**
```powershell
$env:REPLICATE_API_TOKEN = "r8_your_token_here"
```

**Windows — persist for all sessions:**
```powershell
[System.Environment]::SetEnvironmentVariable("REPLICATE_API_TOKEN", "r8_your_token_here", "User")
```

**macOS / Linux:**
```bash
export REPLICATE_API_TOKEN="r8_your_token_here"
```

---

## Commands

### `generate` — single image

```
python fetchmeslop.py generate \
  --prompt "a golden coin icon, pixel art, game UI, transparent background" \
  --name coin-icon \
  --output-dir assets/icons \
  --aspect-ratio 1:1 \
  --format png
```

Output: `assets/icons/coin-icon.png`

Use `--dry-run` to preview the resolved config without calling Replicate:

```
python fetchmeslop.py generate --prompt "..." --dry-run
```

---

### `series` — img2img chained set

Generates N images in sequence.  The **first frame** is a plain text2img; each
subsequent frame uses the previous image as an img2img base so the visual style
(colour palette, line weight, perspective) remains coherent while the prompt
description shifts.

```
python fetchmeslop.py series \
  --prompt-template "an ant at evolution stage {n} of {total}, game sprite, side view" \
  --count 10 \
  --model stability-ai/sdxl \
  --img2img-strength 0.65 \
  --name-prefix ant-stage \
  --name-padding 2 \
  --output-dir assets/ants
```

Output: `assets/ants/ant-stage-01.png` … `assets/ants/ant-stage-10.png`

**Template tokens:**

| Token | Value |
|---|---|
| `{n}` | 1-based frame index |
| `{n0}` | 0-based frame index |
| `{total}` | total frames in the series (`--count`) |
| `{name}` | the `--name-prefix` value |

**img2img strength guide:**

| Value | Effect |
|---|---|
| 0.4–0.5 | Very similar frames (subtle upgrades) |
| 0.6–0.75 | Noticeable changes while preserving style (**recommended**) |
| 0.8–0.95 | Large divergence per step |

#### Resuming an interrupted series

If a series is interrupted mid-run, resume from where it stopped using
`--start-index`.  The tool reads frame `start-index - 1` as the img2img base
and generates all remaining frames without touching the already-saved files:

```
# Original command (stopped at frame 6):
python fetchmeslop.py series --count 10 --name-prefix ant --start-index 1 ...

# Resume from frame 6:
python fetchmeslop.py series --count 10 --name-prefix ant --start-index 6 ...
```

---

### `batch` — multiple jobs from a config file

```
python fetchmeslop.py batch --config batch.yaml
```

#### Example `batch.yaml`

```yaml
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

JSON is also supported (`.json` extension).

---

## Shared Options (all commands)

| Flag | Default | Description |
|---|---|---|
| `--model` | `black-forest-labs/flux-schnell` | Replicate model identifier |
| `--format` | `png` | Output format: `png`, `jpeg`, `webp` |
| `--aspect-ratio` | `1:1` | Preset (`1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `2:1`) or custom `WxH` |
| `--output-dir` | `./output` | Destination folder (created if absent) |
| `--dry-run` | — | Print resolved config and exit without calling Replicate |
| `--verbose` | — | Print Replicate prediction URLs and extra progress info |
| `--overwrite` | — | Replace existing output files |

---

## Model Registry

The built-in registry includes:

| Model | img2img | Notes |
|---|---|---|
| `black-forest-labs/flux-schnell` | ✗ | Fast text2img (default) |
| `black-forest-labs/flux-dev` | ✗ | Higher quality text2img |
| `black-forest-labs/flux-2-pro` | ✗ | Highest quality text2img |
| `stability-ai/sdxl` | ✓ | img2img capable; deprecated on Replicate as of 2025 |
| `stability-ai/stable-diffusion-3.5-large` | ✓ | img2img capable |

> **Series generation requires an img2img-capable model.**  The tool will
> exit with an error and a helpful message if you select a model that does
> not support img2img when `--count > 1`.

### Extending the registry

Drop a `models_extra.yaml` file next to `fetchmeslop.py` to add custom models
without editing the source:

```yaml
# models_extra.yaml
my-org/my-fine-tune:
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
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Missing/invalid `REPLICATE_API_TOKEN` or import error |
| 2 | Invalid arguments |
| 3 | Replicate API error or model does not support img2img |
| 4 | File write error (path exists, permission denied) |

---

## Running the Tests

```
python -m pytest tests/ -v
```

---

## Project Structure

```
FetchMeSlop/
├── fetchmeslop.py       # CLI entry point (generate / series / batch)
├── generator.py         # Core generation logic (single + series)
├── config.py            # GenerateConfig + SeriesConfig dataclasses
├── models.py            # Model registry + models_extra.yaml support
├── utils.py             # Filename helpers, aspect ratio, image download
├── requirements.txt     # Runtime + dev dependencies
├── README.md
├── models_extra.yaml    # (optional) add custom models here
├── output/              # Generated images (created automatically)
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_utils.py
│   └── test_series.py
└── docs/
    └── Spec.md
```
