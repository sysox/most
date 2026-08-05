# AI provider guide

Human-readable companion to [`ai-catalog.yaml`](../ai-catalog.yaml). The
catalog is used by MOST at runtime; this document explains where the data
comes from, which route to use, and what can change. Prices and provider
inventories were reviewed on **2026-08-05** and must be rechecked before a
cost-sensitive or reproducibility-sensitive run.

## Quick choice

| Need | Recommended route | Cost / data boundary |
| --- | --- | --- |
| Private or offline text | [Ollama](https://ollama.com/) on this machine | No provider token charge; data stays local. |
| Repeatable API workflow | MOST `ai-chat` / `ai-embed` | Usage billing depends on provider. |
| Research data in Czech infrastructure | [CERIT-SC / e-INFRA CZ](https://docs.cerit.io/en/docs/ai-as-a-service/introduction) | Institutional service; no per-token user price is published. |
| Repository coding | `cli-chat codex`, `cli-chat claude`, or e-INFRA-routed Claude | Depends on login/API route and workspace policy. |
| Browser/WebUI, documents, tools | [e-INFRA Open WebUI](https://chat.ai.e-infra.cz/) | Requires login; WebUI has its own storage layer. |

## e-INFRA CZ / CERIT-SC

Official pages:

- [AIaaS overview](https://docs.cerit.io/en/docs/ai-as-a-service/introduction)
- [Chat AI and model catalogue](https://docs.cerit.io/en/docs/ai-as-a-service/chat-ai)
- [OpenAI-compatible API](https://docs.cerit.io/en/docs/ai-as-a-service/ai-api)
- [Coding assistants](https://docs.cerit.io/en/docs/ai-as-a-service/llm-integration)
- [MCP servers](https://docs.cerit.io/en/docs/ai-as-a-service/mcp)
- [Data privacy](https://docs.cerit.io/en/docs/ai-as-a-service/chat-ai#data-privacy)
- [Live model status](https://llm.ai.e-infra.cz/status/)
- [Open WebUI](https://chat.ai.e-infra.cz/)

The API endpoint is `https://llm.ai.e-infra.cz/v1`. Models are available only
to eligible MetaCentrum or Masaryk University users. The exact model inventory
is volatile; use maintained aliases in scripts unless an exact model version
is required.

### Maintained aliases

| Alias | Current target documented by e-INFRA | Intended use |
| --- | --- | --- |
| `mini` | `gpt-oss-120b` | General chat and tools |
| `coder`, `agentic` | `qwen3.5-122b` | Coding and agentic workflows |
| `thinker` | `deepseek-v4-flash-thinking` | Reasoning |
| `kimi` | `kimi-k2.7` | Multimodal and tools |
| `glm` | `glm-5.2` | Reasoning and tools |
| `deepseek` | `deepseek-v4-flash` | Chat; reasoning off by default |
| `deepseek-thinking` | `deepseek-v4-flash-thinking` | Chat with reasoning enabled |

The targets are not permanent model-version guarantees. Query exact live
metadata when needed:

```bash
uv run python -m most catalog-audit --provider einfra --show-models
uv run python -m most list-aliases --provider einfra
```

Direct API discovery (requires `CERIT_API_KEY`):

```bash
curl -H "Authorization: Bearer $CERIT_API_KEY" \
  https://llm.ai.e-infra.cz/v1/models | jq '.data[].id'

curl -H "x-litellm-api-key: Bearer $CERIT_API_KEY" \
  https://llm.ai.e-infra.cz/v1/model/info | jq '.data[]'
```

### Embeddings and reranking

The current e-INFRA documentation lists `qwen3-embedding-4b`,
`qwen3-reranker-4b`, `nomic-embed-text-v1.5`, `nomic-embed-text-v2-moe`,
`mxbai-embed-large:latest`, and `multilingual-e5-large-instruct`. MOST
exposes these in the catalog for `ai-embed` or discovery; dimensions and
context sizes are provider metadata, not hard-coded assumptions.

### MCP servers

e-INFRA exposes these HTTP MCP endpoints under
`https://llm.ai.e-infra.cz/<name>/mcp`:

`ddg_search`, `DocFork`, `npmjs`, `prolog`, `solver`, `k8scerit`, `shadcn`,
and `tailwind`.

MOST can attach them to supported CLI routes without changing the user's
persistent configuration:

```bash
uv run python -m most list-mcp-servers
uv run python -m most cli-chat claude --credential-provider einfra \
  --mcp-server DocFork --mcp-server npmjs "Review this repository"
```

Attach only the servers needed for the task because MCP tool descriptions use
context. `ddg_search` is automatically attached to e-INFRA Claude sessions
unless `--no-mcp` is used.

## Claude / Anthropic

Official links:

- [Claude plans and pricing](https://claude.com/pricing)
- [Claude model overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Claude API documentation](https://platform.claude.com/docs/en/home)
- [Claude Code setup](https://docs.anthropic.com/en/docs/claude-code/getting-started)

Current official API list prices at review time (USD per 1M tokens):

| Model | Input | Output | Good fit |
| --- | ---: | ---: | --- |
| Claude Fable 5 | 10 | 50 | Long-running agents |
| Claude Opus 5 | 5 | 25 | Complex coding and enterprise work |
| Claude Sonnet 5 | 2* | 10* | Coding and general work |
| Claude Haiku 4.5 | 1 | 5 | Fast, cost-sensitive work |

`*` Sonnet 5 introductory pricing is listed through 2026-08-31; the standard
price is then $3/$15. Claude web plans and Claude Code subscriptions are
separate from API token billing. Keep the runtime catalog model IDs aligned
with the API model IDs after a provider review.

## OpenAI and Google

- [OpenAI API pricing](https://openai.com/api/pricing/)
- [OpenAI models](https://platform.openai.com/docs/models)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Ollama model library](https://ollama.com/library)

Cloud prices, free tiers, subscriptions, and model availability change often.
MOST therefore keeps prices in `pricing-update.yaml` and requires a reviewed
source URL and date before applying them:

```bash
uv run python -m most catalog-pricing --source pricing-update.yaml
uv run python -m most catalog-pricing --source pricing-update.yaml --update
```

## Local models

Install [Ollama](https://ollama.com/download), then choose models based on
available RAM/VRAM rather than only model names:

```bash
ollama pull granite4.1:3b       # small local chat model
ollama pull ministral-3:8b      # stronger local chat model
ollama pull embeddinggemma:latest  # local embeddings
ollama list
```

MOST treats local Ollama as zero direct token cost and sends requests to
`http://127.0.0.1:11434/v1`. Other local OpenAI-compatible runtimes (vLLM,
LM Studio, llama.cpp server) can use the same adapter pattern when represented
in the catalog. Their actual resource use, license, and quality remain
model/runtime-specific.

## Refresh workflow

1. Refresh dynamic availability: `uv run python -m most catalog-refresh --show-models`.
2. Review the generated `ai-discovered.yaml`; do not copy volatile models into
   the curated catalog without checking the provider source.
3. Review prices separately in `pricing-update.yaml`.
4. Run `uv run pytest` and `uv run ruff check most tests`.
5. Record the exact provider, route, model ID, and execution ID for work that
   needs to be reproducible.

