# Tracing and monitoring

## What is traced

Two sources write to the Application Insights resource connected to the Foundry project.

**Foundry, automatically.** Every run of the agent is traced server-side with no code. See it in the Foundry portal: **Agents → northstar-policy-agent → Traces**. Search there by the response ID that `agent.cli ask` prints.

**This application.** Foundry cannot see what happens inside the search tool, because that code runs here. Two spans add it:

| Span | Records |
|---|---|
| `policy_agent.ask` | Agent name, model that answered, prompt version, decision (answered, not_covered, blocked), whether the answer was verified, cited passage IDs, count of invalid citations, tool calls, tokens, response ID, estimated cost |
| `execute_tool search_policy` | Order and event date used, retrieval backend, retrieved passage IDs, policy versions, rejected references, sub-queries, service time, retrieval tokens |

The tool span is a child of the agent span, so both share one trace ID, which the command prints. Azure SDK calls made inside (the knowledge base request) appear as further children.

## Turning it on

In `.env`:

```
NORTHSTAR_TRACING=azure      # or "console" to print spans locally; unset for none
```

With `azure`, the connection string is read from the Foundry project at run time. It is not stored in `.env`. Spans take two to five minutes to become queryable.

## What is not recorded

Spans carry IDs, counts and outcomes. They do not carry the customer's question, the answer, order contents, tokens or credentials. Setting `NORTHSTAR_TRACE_CONTENT=1` adds the question and answer text; leave it off unless you need it, because anyone with read access to the Application Insights resource can read traces.

Foundry's own server-side traces follow Foundry's settings and may include prompt content. Review that separately.

`northstar.estimated_cost_usd` appears only when `NORTHSTAR_PRICE_INPUT_PER_1M` and `NORTHSTAR_PRICE_OUTPUT_PER_1M` are set. It is an estimate from prices you supply, not a bill.

## Audit records and traces

Business actions are recorded in the tool service's `audit_log` table, which is separate from tracing and is not sampled. Each audit row stores the trace ID of the request that caused it, so an action can be followed from the audit record to its trace.

## Queries

Run these in the Azure portal: Application Insights resource → **Logs**. Application spans are in the `dependencies` table, with attributes under `customDimensions`. All four were run against this project's data on 2026-10-05.

Latency and outcomes:

```kusto
dependencies
| where timestamp > ago(1d) and name == "policy_agent.ask"
| summarize runs = count(), p50_ms = percentile(duration, 50), p95_ms = percentile(duration, 95),
            unverified = countif(tostring(customDimensions["northstar.verified"]) == "False")
  by decision = tostring(customDimensions["northstar.decision"])
```

Search tool errors and retrieval failures:

```kusto
dependencies
| where timestamp > ago(1d) and name == "execute_tool search_policy"
| summarize calls = count(), failures = countif(success == false), p95_ms = percentile(duration, 95),
            rejected = sum(toint(customDimensions["northstar.retrieval.rejected_count"])),
            avg_service_ms = avg(todouble(customDimensions["northstar.retrieval.service_ms"]))
```

`rejected` counts passages the service returned that failed validation: outside their effective dates, unknown, or different from the source text. It should stay at zero; a rise means the index is stale or the filter is not being applied.

Tokens and estimated cost by model and prompt version:

```kusto
dependencies
| where timestamp > ago(1d) and name == "policy_agent.ask"
| summarize input_tokens = sum(tolong(customDimensions["gen_ai.usage.input_tokens"])),
            output_tokens = sum(tolong(customDimensions["gen_ai.usage.output_tokens"])),
            estimated_cost_usd = sum(todouble(customDimensions["northstar.estimated_cost_usd"]))
  by model = tostring(customDimensions["gen_ai.response.model"]), prompt = tostring(customDimensions["northstar.prompt_version"])
```

Which policy versions are being served:

```kusto
dependencies
| where timestamp > ago(1d) and name == "execute_tool search_policy"
| extend version = split(tostring(customDimensions["northstar.policy_versions"]), ",")
| mv-expand version
| summarize uses = count() by tostring(version)
| order by uses desc
```

One trace, end to end (paste the trace ID the command printed):

```kusto
union dependencies, requests, exceptions
| where operation_Id == "<trace id>"
| project timestamp, itemType, name, duration, success, customDimensions
| order by timestamp asc
```

## Alerts worth setting

Create these as log alert rules on the Application Insights resource. Thresholds are yours to choose after watching real traffic; none have been set or measured here.

| Signal | Query basis |
|---|---|
| Unverified answers | `policy_agent.ask` where `northstar.verified == "False"` |
| Rejected references above zero | `northstar.retrieval.rejected_count` |
| Search tool failures | `execute_tool search_policy` where `success == false` |
| p95 latency | `percentile(duration, 95)` on `policy_agent.ask` |
| Blocked requests | `northstar.decision == "blocked"`, which may indicate probing |

## Retention, sampling and cost

Trace retention and billing follow the Application Insights and Log Analytics settings; nothing here changes them. No sampling is configured, which suits a lab. At volume, set a sampling ratio, and remember that audit records are unaffected by it.

## Not yet done

- The tool service (stage 2) does not export spans yet; it links audit rows to a caller's trace when one is supplied.
- Trace context is not propagated from the Foundry service into this process, so Foundry's server-side trace and these spans are separate traces. Join them by response ID.
- No dashboard or alert rule has been created in Azure.
