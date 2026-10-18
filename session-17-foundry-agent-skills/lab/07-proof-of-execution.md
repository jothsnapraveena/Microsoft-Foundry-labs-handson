# Proof of Execution

Use this template to record execution details, observations and measurements for your run.

## Reproduction record

| Field | Recorded value |
| --- | --- |
| Execution date and presenter | |
| Feature status and region | |
| SDK versions and sample/source commit | |
| Target/model/agent versions | |
| Dataset revision or SHA-256 | |
| Instructions/configuration variants | |
| Service job/run/correlation identifiers | |
| Attempts / completions / graded cases | |
| Metrics and denominators | |
| Estimated/actual costs and assumptions | |
| Sanitized output or trace links | |
| Cleanup verification | |

## Observations

Copy [the scorecard template](../evidence/scorecard-template.csv) into an ignored local artifacts directory. Add actual measurements. A blank field means not measured; a zero must be an observed value.

Describe a representative success and any observed failure. Include the expected result, actual result, relevant version and the evidence that supports your interpretation.

## Interpretation

Answer the session question: **Does a versioned skill improve procedural consistency, and can we reproduce behavior after a skill update?**

State what improved, what regressed, what remained unmeasured, and which results came from a small teaching corpus. Do not label the application production-ready based on this exercise alone.

## Local implementation verification

Verified on 2026-10-15: 5 local tests passed using the pinned SDK test environment on Windows/Python 3.14. Run `python -m unittest discover -s tests -v` after installing this session's requirements. See [RUNNING.md](../RUNNING.md) for actual commands. This verifies local behavior and does not change the Azure status above.
