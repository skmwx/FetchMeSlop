# FetchMeSlop — How to Use

A practical guide to generating game UI images from the command line.

---

## Prerequisites

- Python 3.11+
- Dependencies installed: `pip install -r requirements.txt`
- A Replicate API token set in your environment:

  ```powershell
  # Windows PowerShell (current session)
  $env:REPLICATE_API_TOKEN = "r8_your_token_here"
  ```

  ```bash
  # macOS / Linux (current session)
  export REPLICATE_API_TOKEN="r8_your_token_here"
  ```

  Get a token at <https://replicate.com/account/api-tokens>.

---

## The `generate` command

`generate` creates a single image from a text prompt and saves it to disk.

```
python fetchmeslop.py generate --prompt "..." [options]
```

### Minimal example

```powershell
python fetchmeslop.py generate --prompt "a golden coin icon, pixel art, game UI, transparent background"
```

Output: `output/image.png`

---

## Naming the output file

Use `--name` to set the filename stem and `--output-dir` to set the folder.
The folder is created automatically if it does not exist.

```powershell
python fetchmeslop.py generate `
  --prompt "a golden coin icon, pixel art, game UI, transparent background" `
  --name coin-icon `
  --output-dir assets/icons
```

Output: `assets/icons/coin-icon.png`

> **Tip:** If a file with that name already exists, the tool exits with an
> error to avoid overwriting work. Add `--overwrite` to replace it.

```powershell
python fetchmeslop.py generate `
  --prompt "a golden coin icon, pixel art, game UI, transparent background" `
  --name coin-icon `
  --output-dir assets/icons `
  --overwrite
```

---

## Choosing an aspect ratio

Use `--aspect-ratio` with one of the built-in presets, or supply custom pixel
dimensions in `WxH` format.

### Preset reference

| Flag value | Dimensions | Best for |
|---|---|---|
| `1:1` *(default)* | 1024 × 1024 | Icons, avatars, buttons |
| `4:3` | 1024 × 768  | Landscape UI panels |
| `3:4` | 768 × 1024  | Portrait cards, item panels |
| `16:9` | 1024 × 576 | Wide backgrounds, loading screens |
| `9:16` | 576 × 1024 | Mobile backgrounds, splash art |
| `2:1` | 1024 × 512  | Wide banners, headers |
| `WxH` | any | Custom dimensions, e.g. `1280x720` |

### Examples

```powershell
# Wide loading screen background
python fetchmeslop.py generate `
  --prompt "fantasy tavern interior, warm lighting, game background art, detailed" `
  --name tavern-bg `
  --output-dir assets/backgrounds `
  --aspect-ratio 16:9

# Portrait card (item or character)
python fetchmeslop.py generate `
  --prompt "ancient magic scroll, ornate border, game item card art" `
  --name scroll-card `
  --output-dir assets/cards `
  --aspect-ratio 3:4

# Custom size
python fetchmeslop.py generate `
  --prompt "pixel art HUD bar, health indicator, red gradient" `
  --name health-bar `
  --output-dir assets/hud `
  --aspect-ratio 512x128
```

---

## Choosing a model

Use `--model` with a Replicate model identifier (`owner/model`).
The tool has built-in knowledge of these models:

| Model | Speed | Quality | Notes |
|---|---|---|---|
| `black-forest-labs/flux-schnell` *(default)* | Fast (~5–15 s) | Good | Best for iteration |
| `black-forest-labs/flux-dev` | Medium (~20–40 s) | Better | Good balance |
| `black-forest-labs/flux-2-pro` | Medium (~20–40 s) | Best | Highest fidelity |

Any other Replicate model can be specified; the tool will attempt generation
with generic parameters and print a warning.

```powershell
# Use the highest-quality Flux model
python fetchmeslop.py generate `
  --prompt "ornate medieval shield, game icon, detailed metalwork" `
  --name shield-icon `
  --model black-forest-labs/flux-2-pro

# Try a model not in the built-in registry (warning will be shown)
python fetchmeslop.py generate `
  --prompt "..." `
  --model some-author/some-model
```

---

## Choosing an output format

`--format` accepts `png` (default), `jpeg`, or `webp`.

```powershell
python fetchmeslop.py generate `
  --prompt "fantasy forest background, oil painting style" `
  --name forest-bg `
  --format jpeg `
  --aspect-ratio 16:9
```

> **Tip:** Use `png` for UI elements (supports transparency).
> Use `jpeg` or `webp` for large backgrounds where file size matters.

---

## Previewing a run without generating anything

`--dry-run` prints the fully resolved configuration and exits immediately —
no API call is made, nothing is written to disk. Useful for double-checking
settings before spending API credits.

```powershell
python fetchmeslop.py generate `
  --prompt "pixel art sword icon, fantasy RPG, transparent background" `
  --name sword `
  --output-dir assets/weapons `
  --aspect-ratio 1:1 `
  --model black-forest-labs/flux-2-pro `
  --dry-run
```

Example output:

```
Dry-run — resolved configuration
────────────────────────────────────────
  Model               : black-forest-labs/flux-2-pro
  Prompt              : pixel art sword icon, fantasy RPG, transparent background
  Dimensions          : 1024×1024  (--aspect-ratio 1:1)
  Format              : png
  Output              : C:\Playground\FetchMeSlop\assets\weapons\sword.png
  Supports img2img    : False
  Supports neg prompt : False

No API call made (--dry-run).
```

---

## Reproducing a result with a seed

By default the model picks a random seed, so each run produces a different
image. Pass `--seed` to lock the result.

```powershell
# First run — produces a specific image
python fetchmeslop.py generate `
  --prompt "glowing blue gem, game icon, pixel art" `
  --name gem-v1 `
  --seed 1337

# Exact same image again
python fetchmeslop.py generate `
  --prompt "glowing blue gem, game icon, pixel art" `
  --name gem-v1-copy `
  --seed 1337
```

> **Note:** Results are only reproducible on the same model and version.
> Switching `--model` will produce different output even with the same seed.

---

## Verbose mode

`--verbose` prints extra detail: model input dict, the Replicate prediction
URL (so you can inspect the run on replicate.com), and the image download URL.

```powershell
python fetchmeslop.py generate `
  --prompt "wooden treasure chest, game sprite, top-down view" `
  --name chest `
  --verbose
```

---

## Negative prompts

Some models (e.g. SDXL) accept a negative prompt to steer away from
unwanted elements. `--negative-prompt` is silently ignored for models that
do not support it (all current Flux models).

```powershell
# Only meaningful with a model that supports_negative_prompt = True
python fetchmeslop.py generate `
  --prompt "fantasy warrior portrait, detailed armour" `
  --negative-prompt "blurry, watermark, text, low quality" `
  --name warrior `
  --model stability-ai/sdxl
```

---

## Advanced model tuning

`--num-inference-steps` and `--guidance-scale` are passed to the model when
it supports them. Both default to the model's own built-in value, which is
usually the sweet spot — only adjust if you know the model's behaviour.

```powershell
# Flux Dev supports guidance; higher values follow the prompt more strictly
python fetchmeslop.py generate `
  --prompt "isometric castle, game asset, clean edges" `
  --name castle `
  --model black-forest-labs/flux-dev `
  --guidance-scale 4.5 `
  --num-inference-steps 30
```

---

## All options at a glance

```
python fetchmeslop.py generate --help
```

| Flag | Default | Description |
|---|---|---|
| `--prompt` | *(required)* | Text prompt |
| `--name` | `image` | Output filename stem (no extension) |
| `--output-dir` | `./output` | Destination folder |
| `--format` | `png` | `png`, `jpeg`, or `webp` |
| `--aspect-ratio` | `1:1` | Preset or `WxH` |
| `--model` | `flux-schnell` | Replicate model identifier |
| `--negative-prompt` | *(empty)* | What to avoid (model-dependent) |
| `--seed` | random | Fix for reproducibility |
| `--num-inference-steps` | model default | Denoising steps |
| `--guidance-scale` | model default | CFG scale |
| `--overwrite` | off | Replace existing output file |
| `--dry-run` | off | Print config, skip API call |
| `--verbose` | off | Extra progress and URL output |

---

## Output structure

The tool creates the output folder if it does not exist, and writes a single
file per run:

```
{output-dir}/
└── {name}.{format}
```

Example after a few runs:

```
assets/
├── icons/
│   ├── coin-icon.png
│   ├── shield-icon.png
│   └── sword.png
├── backgrounds/
│   └── tavern-bg.jpeg
└── cards/
    └── scroll-card.png
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | `REPLICATE_API_TOKEN` missing or authentication failed |
| `2` | Invalid arguments (bad flag, missing required option) |
| `3` | Replicate API error (network, model error, prediction failed) |
| `4` | File write error (path already exists, permission denied) |

Use these in scripts to detect and handle failures:

```powershell
python fetchmeslop.py generate --prompt "..." --name coin
if ($LASTEXITCODE -ne 0) {
    Write-Error "Generation failed with exit code $LASTEXITCODE"
}
```

---

## Common errors

| Error message | Cause | Fix |
|---|---|---|
| `REPLICATE_API_TOKEN is not set` | Env var missing | Set `$env:REPLICATE_API_TOKEN` |
| `Replicate authentication error` | Token invalid or expired | Get a fresh token from replicate.com |
| `Output file already exists` | File from a previous run | Add `--overwrite` or use a different `--name` |
| `Unrecognised aspect ratio` | Typo in `--aspect-ratio` | Use a preset or `WxH` format (e.g. `1280x720`) |
| `Failed to create prediction: 404` | Model retired or misspelled | Check the model ID on replicate.com |
| `Replicate returned no output` | Model returned empty result | Check the prediction URL on replicate.com |
