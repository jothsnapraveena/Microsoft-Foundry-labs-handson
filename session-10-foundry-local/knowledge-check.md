# Session 10: Knowledge Check

Answer before opening the key.

1. What is the difference between downloading a model and running it?
2. Why record both a model alias and the actual variant reported by the CLI?
3. Your first run succeeds online. Is that sufficient evidence of offline inference? Describe a better check.
4. A draft invents a refund approval despite instructions to use only supplied facts. What failed, and how should you handle the draft?
5. Why should you measure the first run separately from a repeat run?
6. Does exiting an interactive chat prove the model cache was deleted?
7. Your application calls a remote inventory API while using a local model. Which part of the workflow still needs connectivity?
8. An older service-based SDK example uses a fixed localhost port. What should you verify before adapting it?

9. Explain catalog, cached, and loaded states.
10. Why unload in `finally`?
11. What history must the SDK follow-up include?
12. Does native chat need an HTTP endpoint? When is the optional service useful?

<details>
<summary>Answer key</summary>

1. Downloading stores model files; running executes inference and requires runtime resources.
2. The alias identifies your intended model; the resolved variant makes the hardware-specific execution reproducible.
3. No. Complete setup, confirm the cache entry, temporarily disconnect if practical, and submit a new prompt to the cached model. Record the result and limitations.
4. The draft failed the supplied-facts check. Reject or correct it, retain the failing prompt, and rerun it after changes. Prompt instructions alone are insufficient evidence of reliable behavior.
5. Setup, downloading, and loading can distort the first measurement. Keep those observations separate from repeat-response timing.
6. No. Chat exit, runtime shutdown, and cache deletion are separate actions. Inspect the cache afterward.
7. The inventory API call. Local inference does not make every dependency local.
8. Check the installed SDK's current API and service behavior. Service-based clients need endpoint discovery; the current native SDK has a different workflow.

9. Advertised models, locally stored files, and models available in runtime memory, respectively.
10. Release the model after a successful load even if generation fails; this retains cached files.
11. The original user prompt, assistant reply, and new user message.
12. No. Start the service for another process or HTTP client, discover its URLs, and stop it afterward.

</details>
