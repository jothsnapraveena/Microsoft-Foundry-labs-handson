# Sessions 14?19: Implementation Status

All six sessions now include application code, pinned direct dependencies, local tests, configuration examples and executable run guides. Each is independent of Northstar and earlier applications. They use the Foundry SDK and, where relevant, the MCP SDK or Microsoft Responses hosting library.

| Session | Implemented | Verified locally | Live work still pending |
| --- | --- | --- | --- |
| [14: Security](session-14-foundry-agent-security/RUNNING.md) | Prompt-agent variants, fixed corpus, human review summary, managed taxonomy/scan lifecycle, cleanup ledger | 6 tests: review semantics, disclosure flags, SDK prompt definitions and cloud guard | Configure project/models; create agents; review taxonomy; run paired tests/scans |
| [15: Router](session-15-foundry-model-router/RUNNING.md) | ARM deployment helper, alternating paired benchmark, strict JSON grading, latency summaries and optional verified prices | 7 tests: grading, error denominators, ordering and cached-token pricing | Select supported deployments/region; run benchmark; review explanation cases and pricing |
| [16: Toolboxes](session-16-foundry-toolboxes-mcp/RUNNING.md) | SQLite inventory, approved idempotent mock reservations, authenticated MCP HTTP server, MCP probe, toolbox/consumer lifecycle and explicit call approvals | 13 tests including concurrent retries, rollback, strict inputs, bearer rejection and real MCP protocol over stdio | Host reachable HTTPS MCP endpoint; create authenticated project connection; verify toolbox and two consumers |
| [17: Skills](session-17-foundry-agent-skills/RUNNING.md) | Version registration, pinned download/hash verification, explicit skill consumer, baseline/v1/v2 evaluation and promotion | 5 tests plus local artifact validation | Verify Skills preview access; register and download real versions; run model comparison |
| [18: Hosted](session-18-foundry-hosted-agent-observability/RUNNING.md) | Responses protocol server, controlled fault, custom spans, Docker/ACR build, SDK agent deployment/status/invocation/cleanup | 9 tests including an HTTP request through the actual Responses host | Build image in an existing registry; deploy active versions; verify runtime identity and Azure traces |
| [19: Fine-tuning](session-19-foundry-fine-tuning/RUNNING.md) | 160 train/40 validation synthetic examples, split validator, development baselines, SFT submission/status/checkpoints, custom deployment helper and held-out comparison | 6 tests plus actual local preparation/hash manifest | Human data review; check training/deployment eligibility; measure baselines; train and evaluate a selected checkpoint |

## Reproduce local verification

Create an environment per session and install that folder's requirements.txt. Each supports:

~~~powershell
python -m unittest discover -s tests -v
python lab.py plan
~~~

For maintainers with the union of session dependencies installed, run from the repository root:

~~~powershell
python tools/check_sessions_14_19.py
~~~

The runner never invokes cloud commands. It writes clearly labeled local results under each session's ignored artifacts/local-checks.json. It uses subprocesses so independently vendored support modules do not share configuration.

Verification performed on 2026-10-15 using Python 3.14 on Windows: **46 tests passed** and installed dependencies passed pip check. The container targets Python 3.13; Docker build/Linux runtime verification is still pending. SDK serialization and local protocol tests are not live service validation.

## Configure before billed execution

Copy only the relevant session's .env.example to .env and enter its own project/deployment settings. Sign in manually; no login or existing session credentials were assumed. Cloud commands require --confirm. Some commands also require reviewed data/taxonomy flags.

A local test does not prove region/model availability, RBAC, a service API contract, training quality or a successful deployment. Reports preserve errors and unknown measurements. User-owned existing Azure resources are prerequisites; the helper scripts do not create full subscription/project infrastructure.

## Operational limits

These are teaching implementations, not production certifications. The inventory uses a fixed synthetic actor bound to a shared demo token, rather than a complete delegated identity system. The hosted-agent lesson routes a validated read-only function before model synthesis; it is not an arbitrary agent tool-selection loop. Fine-tuning data is deliberately templated and requires review/diversification before real-world claims.

Resource ledgers bind version cleanup to the configured project. Deployment helpers refuse to overwrite existing resources and delete only recorded deployment IDs. Connection/server hosting, taxonomies, completed fine-tuned models and some registry/telemetry artifacts have explicit separate cleanup steps in the run guides.

No Azure model evaluation, automated scan, model training, image build or remote deployment was performed during local verification.
