# Running Session 16

Create an environment, install requirements.txt and run:

~~~powershell
python -m unittest discover -s tests -v
python lab.py plan
python lab.py init
python lab.py stock --sku J-101
~~~

## Local MCP protocol

Copy .env.example to .env. Set MCP_API_TOKEN to a random value of at least 24 characters; do not commit it. The token binds a fixed synthetic actor (MCP_ACTOR_ID, default lab-demo-user). This is a teaching authentication scheme, not end-user delegated authorization.

~~~powershell
python server.py
~~~

In another activated terminal:

~~~powershell
python probe.py --sku J-101
~~~

The probe initializes an actual MCP ClientSession, discovers tools and executes get_stock over streamable HTTP. The server listens on loopback by default. No model is called by the local protocol probe.

## Optional mock reservations

Set ENABLE_MOCK_WRITES=1 before starting the server. Operator approval is a separate local command, never a tool the model can call:

~~~powershell
python lab.py approve --request-id JR-001 --actor lab-demo-user --sku J-101 --quantity 1
~~~

An MCP client may now call reserve_stock with the bound SKU/quantity/request and an idempotency key. The backend rejects unapproved, conflicting, overstock, noninteger and nonpositive requests. Concurrent identical retries produce one stock decrement and one audit row. To reset, use a new database path in tests; do not silently reset an active demo database.

## Foundry toolbox and consumers

Make the server reachable through an authenticated HTTPS endpoint you control. Configure MCP_BIND_HOST appropriately for your hosting environment; review host/proxy protections and TLS there. A hosted agent cannot reach your laptop's localhost.

Create an authenticated remote-tool project connection using the current Microsoft MCP connection guide: its Authorization header must carry the same Bearer token. Set MCP_SERVER_URL and MCP_CONNECTION_ID. This code deliberately reuses an existing Foundry project and connection; it does not provision public MCP hosting or a connection secret.

~~~powershell
python lab.py toolbox --confirm
~~~

Inspect artifacts/toolbox.json and set TOOLBOX_MCP_URL to the created version-specific consumer URL from Foundry. Then:

~~~powershell
python probe.py --toolbox --confirm
python lab.py agents --confirm
python lab.py ask --consumer stock --question "How many J-101 drills are available?" --confirm
~~~

The saved response includes real approval requests. Inspect the actual tool name/arguments, then explicitly approve or deny one:

~~~powershell
python lab.py approval-response --consumer stock --response-id YOUR_RESPONSE_ID --approval-id YOUR_APPROVAL_ID --decision approve --confirm
~~~

Repeat for consumer purchasing to demonstrate reuse. Another approval may be required at a nested boundary; nothing is automatically approved. Inspect saved output until the call completes. Backend approval and MCP call approval are separate controls. Stored service responses may contain synthetic tool data and should be included in retention review.

## Cleanup

~~~powershell
python lab.py cleanup --confirm
~~~

Stop the local server; remove session-owned connections, response data and HTTPS hosting separately. The CLI removes only recorded agent/toolbox versions. Do not delete shared project resources.
