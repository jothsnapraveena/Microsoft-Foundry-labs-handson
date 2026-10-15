# Running Session 17

Create an environment, install requirements.txt and run:

~~~powershell
python -m unittest discover -s tests -v
python lab.py local
~~~

This local command parses both packages and records distinct content hashes. It does not call a model or prove Skills API integration.

Copy .env.example to .env and set the project endpoint and MODEL_DEPLOYMENT. The implementation uses the documented explicit-download consumer: it downloads a pinned skill from Foundry and injects its instructions into a fresh model context. It does not rely on automatic skill discovery or an unsupported prompt-agent skill field.

## Register, consume and evaluate

~~~powershell
python lab.py register --name s17-ticket-triage --confirm
python lab.py evaluate --name s17-ticket-triage --confirm
~~~

The SDK client enables preview support. Registration records immutable service versions for local v1 and v2. Evaluation fetches each exact version through the Skills API, reads one bounded SKILL.md from the archive without extracting paths, verifies the body hash against the registered source, and evaluates baseline/v1/v2 (24 model calls).

The baseline receives no downloaded skill. Each report row records the actual loaded hash, immutable version and model response. A missing or mismatched download aborts the experiment; there is no local-file fallback that could masquerade as service consumption.

Version 1 intentionally lacks the explicit account-compromise escalation procedure. Version 2 adds it. Record actual improvements and regressions; an upload or a content hash alone does not establish quality.

## Default promotion

~~~powershell
python lab.py promote --name s17-ticket-triage --variant v2 --confirm
~~~

The evaluation remains pinned to the versions in its ledger. Changing a default does not silently change those references. The exercise demonstrates explicit loading; toolbox MCP-resource discovery is a different optional integration and is not claimed by this code.

## Cleanup

~~~powershell
python lab.py cleanup --name s17-ticket-triage --confirm
~~~

Only recorded skill versions are removed. Inspect parent/default state and any other consumers before deleting additional resources. Do not discard the ledger until cleanup is verified.
