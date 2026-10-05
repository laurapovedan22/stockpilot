# ADR 006 — Assistant scope

Decision: deterministic offline intent routing, schema-validated read tools, TF-IDF
document references and optional LLM read-tool coordination. Dataset scope is injected by server.
Reason: keep demo costs at zero and calculations auditable without model hallucinations.
Tradeoff: the offline mode supports limited intents; optional model coordination has
strict schemas, four total tool calls and a configurable total deadline.
Imported document instructions never authorize tools. Scenarios require explicit UI execution.
