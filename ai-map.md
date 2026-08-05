# MOST AI map

Quick routing map. The detailed, source-linked inventory is in
[`docs/ai-provider-guide.md`](docs/ai-provider-guide.md); the machine-readable
runtime source is [`ai-catalog.yaml`](ai-catalog.yaml).

| Provider / route | MOST command | Use it for | Data boundary |
| --- | --- | --- | --- |
| Ollama / local | `chat`, `ai-chat`, `ai-embed` | Offline/private drafts, preprocessing, embeddings | Stays on this machine. |
| CERIT-SC / e-INFRA API | `ai-chat`, `cerit-chat`, `ai-embed`, `ai-transcribe` | Research, coding, large models, institutional workflows | e-INFRA CZ infrastructure; exact models rotate. |
| CERIT Open WebUI | `browser-chat cerit --manual` | Interactive model choice, documents, RAG, tools | WebUI login and storage apply. |
| Anthropic API | `ai-chat --provider anthropic` | Repeatable Claude automation | Cloud API and usage billing. |
| Claude Code | `cli-chat claude` | Repository coding and architecture work | CLI login or explicit e-INFRA credential route. |
| OpenAI API / Codex | `ai-chat --provider openai`, `cli-chat codex` | Structured API work and coding | Cloud API or subscription route. |
| Google Gemini | `ai-chat --provider google`, `cli-chat agy` | Multimodal and general reasoning | Cloud API/account route. |

## Practical defaults

- Sensitive data that must not leave the workstation: local Ollama only.
- Approved research data: e-INFRA API, preferably direct API rather than
  WebUI for sensitive workflows.
- Coding with file changes: explicitly use `--writable` and a selected
  workspace; inspect the Git diff afterwards.
- Stable e-INFRA automation: use aliases (`mini`, `coder`, `kimi`, `deepseek`)
  and record the resolved model from `catalog-audit`.
- Cost-sensitive cloud work: refresh the catalog and review
  [`pricing-update.yaml`](pricing-update.yaml) first.

## Commands

```bash
uv run python -m most catalog-audit --provider einfra --show-models
uv run python -m most list-aliases --provider einfra
uv run python -m most list-mcp-servers
uv run python -m most catalog-pricing --source pricing-update.yaml
```

See [`install.md`](install.md) for installation and credentials, and
[`README.md`](README.md) for the complete CLI reference.
