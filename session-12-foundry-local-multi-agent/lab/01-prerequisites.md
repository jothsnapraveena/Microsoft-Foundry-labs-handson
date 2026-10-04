# Prerequisites

Use a supported machine with sufficient memory and disk space for the chosen model. No Azure credentials or resources are required.

From `session-12-foundry-local-multi-agent`, create a separate virtual environment for this session:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/multi_agent_lab.py --help
```

Install exactly one native SDK variant from `requirements.txt`. Use a fresh virtual environment. An environment previously used for the service-based SDK 0.5.1 must be replaced; that package has a different API.

The application downloads its model on first use and keeps it in its own cache at `~/.retail_support_agents/cache/models`. The first run therefore needs a network connection, several gigabytes of disk space and a few minutes. Later runs can add `--offline`.

`--offline` prevents explicit downloads, but SDK initialization may probe catalog endpoints. Validate disconnected startup separately; the flag does not enforce network isolation.
