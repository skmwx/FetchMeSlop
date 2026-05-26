# FetchMeSlop

A Python CLI tool for generating game UI images via the [Replicate](https://replicate.com) API.

> **Current milestone: MVP-01 — API Connection & File Write Smoke Test**
> Runs a single hardcoded generation to confirm the Replicate API token works and that images can be saved to disk.

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

## Running the smoke test (MVP-01)

```
python fetchmeslop.py
```

On success you will see output similar to:

```
FetchMeSlop — MVP-01 smoke test
================================
  Model : black-forest-labs/flux-schnell
  Prompt: a golden coin icon, pixel art, game UI, transparent background

Calling Replicate API… (this may take 30–90 seconds)
Prediction URL : https://replicate.com/p/abc123xyz
Waiting for result…
Downloading image…

Done!
  File           : C:\Playground\FetchMeSlop\output\test.png
  Prediction URL : https://replicate.com/p/abc123xyz
```

The generated image is saved to `output/test.png`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `REPLICATE_API_TOKEN environment variable is not set` | Follow step 4 above |
| `Replicate authentication error` | Verify your token is correct at replicate.com/account/api-tokens |
| `'replicate' package is not installed` | Run `pip install -r requirements.txt` |
| Generation takes very long / times out | Replicate cold-start can be slow for the first request; try again |

---

## Project structure (MVP-01)

```
FetchMeSlop/
├── fetchmeslop.py    # Single-file entry point (MVP-01 smoke test)
├── requirements.txt  # Python dependencies
├── README.md         # This file
├── output/           # Generated images (created automatically)
└── docs/
    └── Spec.md       # Full tool specification
```

Later MVPs will expand this into a proper package with CLI commands, config support, and series generation. See [docs/Spec.md](docs/Spec.md) for the full specification.
