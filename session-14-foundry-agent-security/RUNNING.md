# Running Session 14

Run commands from this directory. Use Python 3.13+ in an isolated environment:

~~~powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe lab.py plan
Copy-Item .env.example .env
~~~

Set this session's project endpoint, target MODEL_DEPLOYMENT. If you have not created them yet, follow the [Azure setup plan](AZURE-SETUP.md). Sign in yourself using your normal Azure identity workflow. No Northstar resources are required.

## Create and compare

~~~powershell
python lab.py create --confirm
python lab.py fixed --limit 1 --report artifacts/smoke.json --confirm
python lab.py fixed --confirm
~~~

These are real SDK calls. The resource ledger stores exact agent versions. The fixed test runs both variants across eight cases (16 target calls). artifacts/fixed.json records outputs and heuristic flags, not an automatic semantic attack-success score.

Fixed runs wait seven seconds between requests by default, matching the small teaching deployment's request quota. Adjust `--request-interval` to your actual rate limits. Reports retain service error codes, HTTP status, and request IDs when supplied. Content-filter rejections remain execution errors with no answer grade; do not count them as successful prompt hardening. Preserve prior reports with a different `--report` path before repeating a run.

Start with the two-call smoke test above. It exercises one legitimate question per variant and does not establish security quality. Proceed to the full corpus after both calls complete successfully. Each observation is checkpointed immediately; interrupted reports retain `execution_status=running`, and any failed target call makes the completed command exit with code 1. Neither a successful execution nor a heuristic flag is a manual quality verdict.

Before inference the runner fetches the recorded deployed versions and verifies their instructions and model against the experiment. Prompt hashes come from those verified definitions. If local instructions have changed, preserve previous reports and explicitly recreate the agent versions before testing; `create` reuses versions already in the ledger rather than silently updating them.

Review each completed row against its expected behavior and set manual_pass to true or false. Do not change errors into passes. Then:

~~~powershell
python lab.py review --report artifacts/fixed.json
~~~

The summary keeps attack and legitimate questions separate and exposes unreviewed counts. Canary matching catches exact/spaced matches only; paraphrased disclosure and fabricated approval require human review.

Assistant reviews use separate `assistant_pass` and `assistant_review_rationale` fields. Summarize those with `--review-source assistant`; this does not populate `manual_pass` or represent human approval. The captured [2026-10-18 evidence](evidence/fixed-2026-10-18.json) contains this separately labeled review.

## Cleanup

~~~powershell
python lab.py cleanup --confirm
~~~

This removes the recorded agent versions and evaluation resources. Inspect remaining session-owned resources and any shared model deployments in the portal. Preserve the ledger on partial failure so cleanup can resume. A failed live call is not a successful capability demonstration.
