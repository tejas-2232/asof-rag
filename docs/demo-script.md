# Three-minute demo

## Setup

- TrueForge hosted mode is healthy at `http://localhost:8791`.
- OpenAI, Daytona, and the AsOfRAG MCP connector are configured.
- The AsOfRAG control room is open at `http://localhost:3000`.
- Use one company with filings on both sides of the selected as-of date.

## 0:00–0:25 — Establish the risk

Show the filing timeline and say:

> Financial RAG can answer a historical question with a later filing because
> vector similarity understands relevance, not when information became public.
> For investment research, that is look-ahead bias.

Select the historical as-of date and run the naive query. Highlight the red
future citation.

## 0:25–1:05 — Let the harness investigate

Start the AsOfRAG agent in the embedded TrueForge panel:

```text
Investigate why the historical query contains future evidence. Build and
evaluate a point-in-time-safe candidate, but do not promote it.
```

Expand the TrueForge steps so the demo visibly shows:

1. SEC MCP filing discovery;
2. trusted section-aware ingestion through the MCP service;
3. generated diagnostic/evaluation code running in Daytona;
4. candidate staging in a separate Qdrant collection.

## 1:05–1:50 — Show measurable improvement

Display production and candidate results side by side:

- measured temporal leakage count;
- measured candidate chunk count;
- citation presence for returned evidence;
- filing date and accession number;
- the exact future citation excluded by the candidate.

Keep the original query and as-of date unchanged.

## 1:50–2:25 — Demonstrate control

Ask the agent to promote the candidate. Pause on TrueForge's approval UI and
explain:

> The agent can investigate and test autonomously, but changing the production
> knowledge index is a controlled action.

Review the candidate version and click **Approve**.

## 2:25–2:50 — Verify production

Repeat the same historical query against production. Show the values actually
returned by the running services:

- zero future citations;
- a historically eligible filing;
- SEC source link and section;
- previous production version retained for rollback.

## 2:50–3:00 — Close

> AsOfRAG is CI/CD and incident response for financial RAG indexes. TrueForge
> provides the real tools, isolated execution, parallel investigation,
> persistent session, and approval boundary.

End on the architecture view or the production promotion receipt.
