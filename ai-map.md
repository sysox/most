# MOST AI map

This is the current provider map for this workstation. It describes the
verified access routes and recommended use, not a claim that every provider
supports every capability in every account or model version.

## Provider map

| Provider / location | MOST route | Current verified models or account | Best use | Privacy and limits |
| --- | --- | --- | --- | --- |
| Ollama / local machine | `chat` | `granite4.1:3b`, `ministral-3:8b`, `embeddinggemma:latest` | Offline drafts, private text, quick experiments, embeddings, local preprocessing | Data stays on this machine. Quality and context are limited by local hardware/model. |
| OpenAI / cloud | `cli-chat codex` | Codex CLI subscription | Coding, repository inspection, refactoring, tests, terminal-aware development | Requires Codex login. Cloud provider policies and retention apply. Use workspace/privacy controls before sending sensitive data. |
| Anthropic / cloud | `cli-chat claude` | Claude CLI subscription | Long-form analysis, architecture review, documentation, coding assistance | Requires Claude CLI login. Cloud provider policies and retention apply. |
| Google/Gemini through Antigravity / cloud | `cli-chat agy` | Antigravity CLI account and available Gemini model | General reasoning, research-style drafting, multimodal or Gemini-specific work | Requires Antigravity login. Headless tool permissions may need configuration. Cloud provider policies and retention apply. |
| Gemini for Education / Google Workspace | `browser-chat gemini` | Institution-managed Gemini for Education account; provider selects available models | Education, multimodal assistance, research and coding within an approved Workspace account | Included with qualifying education editions. Google states that Education core-service data is not human-reviewed or used to train models; administrator settings and institution terms still apply. |
| CERIT-SC / e-INFRA CZ | `cerit-chat` | Maintained aliases such as `mini`, `coder`, `agentic`, `kimi`, `glm`, `deepseek` | Research, coding, large-context work, sensitive institutional data, multimodal/tool-capable models | Requires CERIT/e-INFRA account and API key. Requests remain within e-INFRA CZ infrastructure according to its documentation; CERIT service-side retention still applies. |
| CERIT Open WebUI / e-INFRA CZ | `browser-chat cerit --manual` | `https://chat.ai.e-infra.cz` | Interactive model selection, document/RAG workflows, image and tool-enabled WebUI use | Requires manual e-INFRA login. MOST records the prompt and pasted response; WebUI may retain its own conversation copy. |

## Recommended routing by action

| Action | First choice | Fallback | Reason |
| --- | --- | --- | --- |
| Fully offline or highly private text | Ollama `ministral-3:8b` | Ollama `granite4.1:3b` | Keeps data on the workstation. |
| Fast local classification, extraction, or preprocessing | Ollama `granite4.1:3b` | Ollama `ministral-3:8b` | Smaller model and low network dependency. |
| Embeddings and semantic search preparation | Ollama `embeddinggemma:latest` | CERIT embedding API | Local embedding avoids sending source text elsewhere. |
| Coding in this repository | Codex CLI | Claude CLI, then CERIT `coder` | Codex is already verified with MOST and is terminal/repository oriented. |
| Code review and architecture discussion | Claude CLI | Codex CLI or CERIT `coder` | Good fit for long explanations and design critique. |
| Large-context research or institutional work | CERIT `deepseek`, `kimi`, or `thinker` | Claude CLI | Keeps the request in the research infrastructure and supports large models. |
| General cloud reasoning | Antigravity/Gemini | Claude or Codex | Use the account and model best suited to the task. |
| Document/RAG work through a GUI | CERIT Open WebUI | Local Ollama workflow | WebUI provides model selection, document handling, and tools. |
| Internet-assisted research | Antigravity/Gemini or CERIT WebUI tools | Claude/Codex if enabled | Explicitly mark that external web content may enter the conversation. |
| Repeatable scripted workflow | CERIT API or Ollama API | Codex/Claude CLI | API/HTTP routes are easier to automate deterministically than browser UI. |
| Sensitive source code that must not leave the machine | Ollama | — | Do not route it to cloud or e-INFRA without an approved data policy. |

## MOST commands

```bash
# Local Ollama
uv run python -m most --data-root ./application-data \
  chat --model ministral-3:8b "Review this text"

# OpenAI Codex CLI
uv run python -m most --data-root ./application-data \
  cli-chat codex --allow-unknown-connectivity "Review this code"

# Claude CLI
uv run python -m most --data-root ./application-data \
  cli-chat claude --allow-unknown-connectivity "Explain this design"

# Gemini through Antigravity
uv run python -m most --data-root ./application-data \
  cli-chat agy --allow-unknown-connectivity "Generate research ideas"

# CERIT/e-INFRA API; CERIT_API_KEY must already be exported
uv run python -m most --data-root ./application-data \
  cerit-chat --model coder "Review this code"

# CERIT Open WebUI, with manual login and copy/paste relay
uv run python -m most --data-root ./application-data \
  browser-chat cerit --manual
```

## Selection rules for future automation

1. Check data sensitivity before selecting a provider.
2. Prefer local Ollama when network transfer is prohibited.
3. Prefer CERIT for approved research data that may use institutional
   infrastructure but should not go to commercial cloud providers.
4. Prefer the CLI providers for coding tasks requiring terminal or repository
   context.
5. Prefer API routes for automation and browser routes for interactive WebUI
   features.
6. Record the provider, route, model alias, and resulting execution ID in
   MOST. CERIT aliases are preferable to volatile exact model names.

Provider capabilities and model availability can change. Before important or
reproducibility-sensitive work, query the provider and record the exact model
identifier in the MOST journal.
