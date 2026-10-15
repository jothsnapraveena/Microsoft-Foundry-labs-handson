# Demo MCP Server Contract

This contract is implemented by ../inventory.py and ../server.py. Start it using ../RUNNING.md; these files do not claim a deployed public endpoint.

## Required read tool

Name: `get_stock`. Input object: exactly `sku`, a nonempty string matching `J-[0-9]{3}`. Reject additional fields and incorrect types.

For a known SKU, return `sku`, `name`, `available_quantity` (nonnegative integer), and `snapshot_utc` from [the catalog](../data/inventory.json). For an unknown SKU return a structured `unknown_sku` result without invented stock.

The server must advertise this contract through MCP tool discovery and execute it through the protocol implementation. An ordinary HTTP route returning JSON is not sufficient to claim MCP compatibility.

## Optional mock write

Name: `reserve_stock`. Inputs: `sku`, positive integer `quantity`, nonempty `request_id` and `idempotency_key`. Caller identity and an approved proposal are established by authenticated application state, never by free-form user claims or an LLM-generated boolean.

Before mutation verify identity, approved proposal binding to SKU/quantity/caller, available stock and idempotency. Reject conflicting reuse of a key. A duplicate identical request returns the original result without decrementing stock again.

Return a mock reservation ID and status only after persisting the synthetic record. Keep a durable audit row with request and actor IDs; do not log credentials. A failed or unapproved request must not mutate stock.

## Exercise records

If enabling writes, create one explicitly approved synthetic proposal JR-001 for one J-101 unit. Replaying it must produce one net decrement. Restore the catalog between experiments and document that this is a mock reservation, not a real commercial transaction.
