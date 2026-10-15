# Running Session 14

Run commands from this directory. Use Python 3.13+ in an isolated environment:

~~~powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe lab.py plan
Copy-Item .env.example .env
~~~

Set this session's project endpoint, target MODEL_DEPLOYMENT and EVALUATION_MODEL_DEPLOYMENT. Sign in yourself using your normal Azure identity workflow. No Northstar resources are required.

## Create and compare

~~~powershell
python lab.py create --confirm
python lab.py fixed --confirm
~~~

These are real SDK calls. The resource ledger stores exact agent versions. The fixed test runs both variants across eight cases (16 target calls). artifacts/fixed.json records outputs and heuristic flags, not an automatic semantic attack-success score.

Review each completed row against its expected behavior and set manual_pass to true or false. Do not change errors into passes. Then:

~~~powershell
python lab.py review --report artifacts/fixed.json
~~~

The summary keeps attack and legitimate questions separate and exposes unreviewed counts. Canary matching catches exact/spaced matches only; paraphrased disclosure and fabricated approval require human review.

## Managed red teaming

~~~powershell
python lab.py taxonomy --variant hardened --confirm
~~~

Inspect artifacts/taxonomy.json and the generated taxonomy in Foundry. Review/edit the prohibited-actions taxonomy with the current service workflow. The saved file is a review artifact, not an API for silently approving generated policy.

After review, supply the actual approved taxonomy resource identifier:

~~~powershell
python lab.py scan --variant hardened --taxonomy-id YOUR_REVIEWED_TAXONOMY_ID --taxonomy-reviewed --confirm
python lab.py scan-status --eval-id YOUR_EVAL_ID --run-id YOUR_RUN_ID --confirm
~~~

The scan uses a small Flip-strategy, two-turn configuration and the documented built-in prohibited-actions/task-adherence evaluators. Availability, attack budgets and evaluator behavior depend on the service; preview compatibility is not established by local tests. To compare managed scans, repeat taxonomy/scan for baseline with matched settings, keeping the two run IDs. Do not mix these rates with the fixed corpus.

## Cleanup

~~~powershell
python lab.py cleanup --confirm
~~~

This removes recorded agent versions and evaluations, requesting cancellation for active scans. Inspect remaining taxonomy resources and any shared model deployments in the portal. Preserve the ledger on partial failure so cleanup can resume. A failed live call is not a successful capability demonstration.
