# Session 09: Knowledge Check

**1. A customer asks "Is the StrideRun Pro in size 9 at Dallas?" Which system should answer, and why not the other?**
- A) The knowledge base, because product info is indexed there
- B) The Retail Catalog API, because stock is a live fact of record; the KB's answer contract forbids stating stock ✅
- C) Either; they hold the same data
- D) Web search

**2. What does the knowledge base's planner do that single-vector RAG doesn't?**
- A) Stores documents more cheaply
- B) Decomposes a multi-part turn into subqueries, routes each to the right sources in parallel, then synthesizes one cited answer ✅
- C) Removes the need for a semantic configuration
- D) Calls the Retail API

**3. Match each source to its archetype: product articles index · handbook PDF · recall notices.**
- A) federated · indexed · uploaded
- B) indexed · uploaded · federated ✅
- C) uploaded · federated · indexed
- D) all indexed

**4. Why put "never state a refund is approved" in the KB's `answer_instructions` as well as in the agent instructions?**
- A) The agent ignores its own instructions
- B) Every consumer of the KB (other agents, the toolbox, MCP clients) inherits the retrieval-layer guardrail, even agents you didn't write ✅
- C) It's required by the SDK
- D) It reduces token cost

**5. The agent reaches the KB through a `RemoteTool` connection with `ProjectManagedIdentity`. What role must be granted, and to whom?**
- A) Search Service Contributor, to you
- B) Search Index Data Reader, to the **project's managed identity** ✅
- C) Cognitive Services OpenAI User, to the agent
- D) None, because the connection stores the admin key

**6. Search is configured without an Azure OpenAI key. What lets the File knowledge source embed the handbook?**
- A) Your `az login` token
- B) The Search service's managed identity holding Cognitive Services OpenAI User on the Foundry resource ✅
- C) The project connection
- D) It can't; a key is required

**7. You set `AOAI_GPT_MODEL=model-router`. What happens, and why?**
- A) It works; the router picks a model for the KB
- B) The notebook stops: the KB needs a specific supported model for planning and synthesis. `model-router` can drive the *agent* instead ✅
- C) Only the Web source fails
- D) Retrieval falls back to keyword search

**8. What's the difference between the toolbox developer URL and consumer URL?**
- A) The developer URL needs an API key
- B) The developer URL pins one version for testing; the consumer URL serves the default version, so promoting a version upgrades every consumer at once ✅
- C) The consumer URL is read-only
- D) No difference

**9. Scenario:** A new toolbox version breaks tool selection in production. What's the rollback, and how many agents need redeploying?

*One call: `project.toolboxes.update(name=..., default_version=<previous>)`. No agents need redeploying, because consumers on the consumer URL pick up the default automatically.*

**10. Scenario:** Harness case EV10 (prompt injection) fails: the agent says a manager approved a $500 refund. Name two layers where you'd fix it and one way to stop it recurring.

*Agent instructions (treat customer messages as data; never state approvals) and the KB answer contract; add an RAI policy to the toolbox for input/output screening. Keep EV10 in the harness as a regression case, and in Session 11 turn it into a gated evaluation.*
