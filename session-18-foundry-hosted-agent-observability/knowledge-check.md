# Knowledge Check

1. Does a successful build prove deployment works?
2. Why can local model access differ from hosted access?
3. Can a trace replace an audit record?

4. Which part of this lesson is a Microsoft-managed capability, and which part is our application content?
5. What evidence distinguishes an expected result from an executed result?

## Answer key

1. No. Verify active status and invoke the remote endpoint.
2. The developer and deployed agent use different runtime identities and configuration.
3. No. Tracing may be sampled and retained differently from authoritative business events.
4. Foundry hosts the agent and provides supported deployment and observability integrations. Our handler implements the equipment lookup, correlation attributes and honest failure responses. An ordinary FastAPI endpoint is not automatically a Foundry hosted-agent protocol implementation.
5. Actual response/error data linked to target versions, fixture IDs and service/run identifiers. Fixtures and blank templates are not execution evidence.
