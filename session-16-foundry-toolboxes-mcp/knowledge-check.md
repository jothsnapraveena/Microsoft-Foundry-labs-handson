# Knowledge Check

1. Does a toolbox implement inventory rules?
2. Why test tools/list through the toolbox?
3. Does reusing a toolbox share memory?

4. Which part of this lesson is a Microsoft-managed capability, and which part is our application content?
5. What evidence distinguishes an expected result from an executed result?

## Answer key

1. No. The backend owns stock and authorization rules.
2. A working direct server does not verify toolbox configuration or its consumer endpoint.
3. No. Tool configuration reuse and conversation state are separate concerns.
4. Foundry supplies the toolbox resource and supported MCP integration. The MCP server must implement validation, stock constraints, authorization and idempotency. An agent approval prompt is not a substitute for backend authorization.
5. Actual response/error data linked to target versions, fixture IDs and service/run identifiers. Fixtures and blank templates are not execution evidence.
