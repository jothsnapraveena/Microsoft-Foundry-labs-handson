# Equipment Lookup Function

assistant.py implements a read-only `get_checklist(device_id)` function inside the chosen supported hosted-agent sample. Use [equipment.json](../data/equipment.json).

- Accept a nonempty string device ID; reject incorrect types and extra arguments.
- For W-101 and W-102 return exactly the matching checklist and device ID.
- For an unknown device return an explicit unknown result without fabricated items.
- For DEMO-FAIL raise a controlled tool error with safe code `DEMO_LOOKUP_FAILURE`.
- Do not disable the controlled fault when demonstrating a better error-handling version; the improvement is honest failure handling, not a pretend successful lookup.
- Add a lookup span with device ID, outcome and safe error code. Do not add credentials or complete user prompts.
- The surrounding host must implement the selected Foundry protocol using its maintained library/sample. server.py wraps this function in the Microsoft Responses protocol host; Dockerfile packages it for hosting.

For the recovery exercise, map the controlled exception to a useful user-facing failure message while preserving the diagnostic code in telemetry. Verify a subsequent healthy request succeeds without leaked request state.
