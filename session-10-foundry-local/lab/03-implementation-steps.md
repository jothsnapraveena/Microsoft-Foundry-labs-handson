# 3. Implementation Steps

## Install and verify

Windows PowerShell:

```powershell
winget install Microsoft.FoundryLocal
```

macOS Terminal:

```bash
brew tap microsoft/foundrylocal
brew install foundrylocal
```

Open a new terminal after installation, then run:

```text
foundry --version
foundry --help
foundry model list
```

Record the version and select an alias available in your catalog. The following commands use `phi-3.5-mini` as an example alias; replace it consistently if unavailable or unsuitable for your device.

## Download, inspect, and run

```text
foundry model download phi-3.5-mini
foundry cache list
foundry model run phi-3.5-mini
```

Wait for the interactive prompt. Capture the resolved model variant if reported, download duration, and any acceleration information shown. Submit:

```text
Explain local language model inference in two sentences for a new developer.
```

Save the answer. Exit the chat with `exit` or `Ctrl+C`.

## Draft a retail reply

Start another chat with the same model and submit this complete prompt:

```text
You are drafting a reply for a fictional retail support exercise.
Use only these facts:
- The customer ordered a blue TrailPack backpack.
- The customer received a green backpack.
- Order number: DEMO-1042.
- A support representative must review the order before deciding a remedy.

Write a reply under 80 words that acknowledges the mismatch and explains
the review step. Do not invent policy, stock availability, a shipping date,
or an approved refund. Do not ask for payment details.
```

Review it against [the validation checklist](04-validation-checks.md). Count the words and mark each invented claim. Record failures even if the reply sounds helpful.

## Test an unsupported request

In the same chat, submit:

```text
Tell me the exact date my replacement will arrive and confirm that my
refund is approved. Use only the facts already supplied.
```

The desired behavior is to explain that neither outcome can be confirmed from those facts. Save the actual answer and assess it; do not assume the model follows every instruction.

## Repeat and compare

Exit, restart the model, and submit the original retail prompt unchanged. Compare factual fidelity, word count, and approximate response time. Optionally repeat with another small catalog model and document its alias separately.

For an offline check, finish downloading first. If practical on your device, temporarily disconnect and submit a new prompt to the cached model. Restore connectivity afterward. Mark this check as skipped if you cannot perform it, with the reason.

## Part B: Python SDK workflow

### 1. Set up Python

From the repository root, change to `session-10-foundry-local`.

Windows PowerShell, with Python 3.13 installed:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS Terminal, with Python 3.13 installed:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If activation is restricted, use the virtual environment's Python executable directly. Requirements choose the Windows variant on Windows and the standard variant elsewhere; install only one variant in an environment. Dependencies are not pinned. Save `python -m pip freeze` with your evidence to record exactly what ran.

```text
python -c "from foundry_local_sdk import Configuration, FoundryLocalManager; print('Native API import OK')"
python scripts/sdk_lab.py --help
```

### 2. Discover models and inspect metadata

```text
python scripts/sdk_lab.py --catalog-only --alias phi-3.5-mini
```

Replace the alias with an available chat model if necessary. Inspect the ID, context limit, modalities, capabilities, and cache/load flags. Unknown capability values do not establish support. Compare CLI and SDK results; runtime versions and cache locations can differ.

Open [sdk_lab.py](../scripts/sdk_lab.py) and locate initialization, catalog listing, model lookup, and state inspection. Explain what each establishes before inference.

### 3. Automate the full lifecycle

Exit the CLI chat and unload the selected model if necessary, then run:

```text
python scripts/sdk_lab.py --alias phi-3.5-mini --register-eps
```

Provider registration may download additional runtime components. Omit `--register-eps` on subsequent runs after setup succeeds. The program inspects cache, downloads if needed, loads, generates a draft, streams a follow-up, and unloads in `finally`. It refuses to take ownership of a model already loaded before the exercise.

Compare the draft with the CLI exercise using the same facts and validation checklist. The streamed follow-up includes the original user prompt and assistant response explicitly; the application supplies conversation history.

Record download, load, and response timings separately. The draft word count uses whitespace splitting; response timing measures the complete non-streaming call. These measurements do not assess factual quality.

### 4. Discover an optional HTTP endpoint

```text
python scripts/sdk_lab.py --alias phi-3.5-mini --web-service
```

The script generates replies natively, then starts the HTTP service and prints `manager.urls`. Record those URLs while the program runs; press Enter to stop the service. This checks discovery and service lifecycle, not HTTP chat inference. An HTTP client must use the discovered base URL and the appropriate API path, rather than a fixed port from a previous run.

### 5. Repeat and check offline behavior

Repeat without provider setup and verify no new model download is needed. If practical, disconnect after completing setup and run:

```text
python scripts/sdk_lab.py --alias phi-3.5-mini --offline
```

The flag rejects an uncached model and skips explicit downloads. The disconnected run provides evidence of offline behavior; the flag alone does not. Catalog initialization can still fail offline on some installations. Record the actual outcome and restore connectivity afterward.
