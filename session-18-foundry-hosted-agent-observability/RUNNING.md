# Running Session 18

Create an environment, install requirements.txt and run:

~~~powershell
python -m unittest discover -s tests -v
python lab.py local --handler v1 --report artifacts/baseline-local.json
python lab.py local --handler v2 --report artifacts/recovery-local.json
~~~

Local mode exercises real Python lookup/failure behavior. It does not call a model or demonstrate Azure hosting. V1 raises the controlled fault; v2 honestly reports it. Neither version fabricates a successful checklist.

## Actual Responses protocol

~~~powershell
python server.py --local
~~~

The server uses Microsoft's ResponsesAgentServerHost and /responses protocol, not an ordinary chat-shaped web endpoint. It listens on port 8088. Local state is kept under ignored artifacts/agentserver. Send:

~~~powershell
Invoke-RestMethod -Uri http://127.0.0.1:8088/responses -Method Post -ContentType application/json -Body '{"input":"Get W-101","stream":false,"store":false}'
~~~

--local explicitly suppresses model calls. Without it, the handler requires Azure configuration and performs a real model call after successful lookup. Unknown/failed lookups bypass synthesis. Lookup is application-routed from a validated device ID; the model does not decide arbitrary tool calls.

## Build and deploy

Copy .env.example to .env. Configure the project, MODEL_DEPLOYMENT, an existing ACR_NAME and a unique AGENT_IMAGE tag in that registry. Sign in manually and verify current hosted-agent/registry permissions.

~~~powershell
python build_image.py --tag s18-willow:demo --confirm
python lab.py deploy --handler v1 --confirm
python lab.py status --confirm
~~~

The build uses Azure CLI's ACR remote build. Dockerfile excludes .env and artifacts. Deployment records the exact agent version, requests a real Responses-protocol container and uses its platform identity to call the configured model. Registry hosting, compatible region and runtime permissions are prerequisites, not automatically created by this script.

Wait until active, then:

~~~powershell
python lab.py ask --question "Get W-101" --confirm
python lab.py ask --question "Get DEMO-FAIL" --confirm
python lab.py deploy --handler v2 --confirm
python lab.py status --confirm
python lab.py ask --question "Get DEMO-FAIL" --confirm
~~~

Compare the actual remote versions. If the SDK reports startup/image/identity failure, keep that failure as evidence instead of claiming deployment succeeded.

## Traces

Server auto-observability is disabled so local imports do not export telemetry unexpectedly. The entry point configures an explicit console exporter or Application Insights when a connection string is supplied by the hosting platform. Use TRACE_EXPORT=console locally. The custom spans include device ID, handler version and safe error code; the model receives only successful lookup facts.

Use queries.kql in the connected Application Insights resource, verifying the exporter table mapping. Check native SDK/server content capture separately. Responses persistence is a teaching setup; durable recovery, tenant partitioning, admission control and production audit are outside this lab.

## Cleanup

~~~powershell
python lab.py cleanup --confirm
~~~

Delete session-only registry images/compute and telemetry resources separately. The CLI removes recorded agent versions; local tests do not verify remote deletion.
