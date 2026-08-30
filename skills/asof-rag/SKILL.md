---
name: asof-rag
description: Curate, evaluate, and safely promote point-in-time financial filing indexes.
---

# AsOfRAG operating procedure

Use this skill whenever a user asks to ingest an SEC filing, investigate a
historical retrieval, compare production with a candidate index, or promote an
index.

## Non-negotiable controls

1. Treat `filed_at` as knowledge time. For an as-of query, evidence with
   `filed_at > as_of` is ineligible even when it is semantically closer.
2. Never overwrite the production index in place. Build an isolated candidate,
   evaluate it, and request approval before promotion.
3. Preserve every citation's ticker, form, accession number, filing date,
   report date, source URL, section, content hash, and index version.
4. Do not claim that a retrieval is point-in-time safe unless the temporal
   leakage count is zero.
5. Use SEC data only for research and clearly state that outputs are not
   investment advice.

## Required workflow

### 1. Resolve the source

- Call `list_filings` to find the requested company's filing versions.
- Call `get_filing_source` for the chosen accession number.
- Explicitly distinguish report date from filing date.

### 2. Build through the trusted ingestion path

Call `build_candidate` with the selected ticker, form, and accession. The MCP
service is responsible for:

- downloading the public filing source;
- extracting section-aware text while retaining headings;
- normalizing whitespace and removing navigation boilerplate;
- creating deterministic content hashes;
- producing bounded, section-aware chunks;
- writing vectors and full provenance to an isolated Qdrant collection.

Use Daytona for generated diagnostics or evaluation scripts and save their
output as `evaluation.json`. Do not execute generated code on the TrueForge
host, and do not send SEC or model credentials into the sandbox.

### 3. Delegate independent checks

When dynamic subagents are available, delegate:

- temporal integrity: search for future-dated evidence;
- document quality: empty, duplicate, or oversized chunks;
- retrieval quality: citation coverage and expected-section hits;
- release safety: candidate isolation and rollback readiness.

Only concise findings should return to the root agent.

### 4. Evaluate before staging

Run deterministic diagnostic checks in the sandbox:

- every candidate chunk has required provenance;
- no duplicate content hashes exist within one filing version;
- `filed_at <= as_of` for every result in the safe retrieval set;
- expected sections appear in top-k for the evaluation questions;
- citations resolve to SEC source URLs.

If any check fails, explain the evidence and rebuild a replacement candidate
rather than weakening the check. Candidate collections are immutable and never
overwrite production.

### 5. Compare and promote

- Call `compare_retrieval` with the same query against naive, production, and
  candidate retrieval.
- Present the temporal leakage count and citations before asking to promote.
- Call `promote_candidate` only when the user explicitly approves. This tool is
  intentionally marked write/destructive so TrueForge must pause.
- After promotion, repeat the as-of query and confirm zero future citations.

## Presentation

Prefer a compact generative UI containing:

- production and candidate metric cards;
- a filing timeline anchored on the as-of date;
- red future citations and green eligible citations;
- the candidate version and approval state.

Always separate measured values from model judgments.
