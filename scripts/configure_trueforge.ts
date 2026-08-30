const TRUEFORGE_URL = process.env.TRUEFORGE_URL ?? "http://localhost:8791";
const MCP_URL =
  process.env.ASOFRAG_MCP_URL ?? "http://host.docker.internal:8000/mcp";
const REPOSITORY_URL =
  process.env.ASOFRAG_REPOSITORY_URL ??
  "https://github.com/tejas-2232/asof-rag";
const SKILL_REF = process.env.ASOFRAG_SKILL_REF ?? "init-branch";
const AGENT_NAME = "asof-rag";

type JsonObject = Record<string, unknown>;

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${TRUEFORGE_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...init.headers,
    },
  });

  const body = (await response.json().catch(() => ({}))) as JsonObject;
  if (!response.ok) {
    throw new Error(
      `${init.method ?? "GET"} ${path} failed (${response.status}): ${JSON.stringify(body)}`,
    );
  }
  return body as T;
}

async function main() {
  const models = await request<{ data: Array<{ name: string }> }>(
    "/api/v1/models",
  );
  const requestedModel = process.env.TRUEFORGE_MODEL;
  const model =
    models.data.find((item) => item.name === requestedModel) ??
    models.data.find((item) => item.name === "openai/gpt-5-4-mini") ??
    models.data[0];

  if (!model) {
    throw new Error(
      "No model is configured. Add a provider in TrueForge Settings → Models.",
    );
  }

  await request("/api/v1/settings/mcp-servers", {
    method: "PUT",
    body: JSON.stringify({
      manifest: {
        type: "remote",
        name: "asof-rag",
        url: MCP_URL,
        description:
          "SEC filing discovery, point-in-time retrieval, candidate evaluation, and approval-gated index promotion.",
      },
    }),
  });

  await request("/api/v1/settings/skills", {
    method: "PUT",
    body: JSON.stringify({
      manifest: {
        type: "git",
        name: "asof-rag",
        url: REPOSITORY_URL,
        path: "skills/asof-rag",
        ref: SKILL_REF,
        description:
          "Curate, evaluate, and safely promote point-in-time financial filing indexes.",
      },
    }),
  });

  const manifest = {
    model: {
      name: model.name,
      params: { reasoning_effort: "medium" },
    },
    instructions: [
      "You are AsOfRAG, a financial RAG reliability engineer.",
      "Prevent look-ahead bias by treating filing date as knowledge time.",
      "Use the asof-rag skill for every ingestion, historical query, candidate evaluation, or promotion.",
      "Run generated parsing and deterministic evaluation code in the Daytona sandbox.",
      "Delegate temporal integrity, document quality, retrieval quality, and release safety checks to focused subagents.",
      "Never promote a candidate with temporal leakage or missing provenance.",
      "Never provide investment advice.",
    ].join(" "),
    mcp_servers: [
      {
        name: "asof-rag",
        enable_tools: ["@all"],
        disable_tools: [],
        preload_tools: ["list_filings", "compare_retrieval"],
        require_approval_for_tools: ["promote_candidate"],
        preload: false,
      },
    ],
    skills: [{ name: "asof-rag" }],
    config: {
      iteration_limit: 80,
      sandbox: { enabled: true, file_downloads: true },
      dynamic_sub_agents: { enabled: true },
      context_management: {
        compaction: { enabled: true },
        large_tool_response: { enabled: true },
      },
      generative_ui: { enabled: true },
      ask_user_questions: { enabled: true },
    },
  };

  const agents = await request<{
    data: Array<{ id: string; name: string }>;
  }>("/api/v1/agents");
  const existing = agents.data.find((agent) => agent.name === AGENT_NAME);

  if (existing) {
    await request(`/api/v1/agents/${existing.id}`, {
      method: "PUT",
      body: JSON.stringify({ manifest }),
    });
    console.log(`Updated TrueForge agent "${AGENT_NAME}" using ${model.name}.`);
  } else {
    await request("/api/v1/agents", {
      method: "POST",
      body: JSON.stringify({ name: AGENT_NAME, manifest }),
    });
    console.log(`Created TrueForge agent "${AGENT_NAME}" using ${model.name}.`);
  }

  console.log(`MCP: ${MCP_URL}`);
  console.log(`Skill: ${REPOSITORY_URL}/tree/${SKILL_REF}/skills/asof-rag`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
