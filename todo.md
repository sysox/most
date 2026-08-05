# MOST — current TODO

This file contains only unfinished or deliberately deferred work. Completed
implementation notes belong in Git history, tests, or the relevant design
document.

## Open

- [ ] Verify whether e-INFRA offers a stable standalone API for image
  generation and speech synthesis. Keep these routes rejected until the
  contract is documented and tested.
- [ ] Consider a LiteLLM-based common client when another provider is added or
  the current provider-specific clients become costly to maintain. Do not do
  this as a speculative refactor.
- [ ] Add full submodule, Git LFS, and Windows path-limit handling in
  Workspace Mode; this remains a design-level gap.

## Current decisions

- e-INFRA uses `CERIT_API_KEY`, OpenAI-compatible API routes, maintained model
  aliases, and the OS keyring; exact model versions are volatile.
- Sensitive workloads require an explicit catalog policy; browser/WebUI
  routes are blocked for them. Direct e-INFRA API access is the preferred
  institutional route.
- `cli-chat codex` is read-only by default. File changes require an explicit
  writable workspace and must be checked with Git.
- e-INFRA MCP servers are selected explicitly; `ddg_search` is the only
  automatic default for e-INFRA Claude sessions.
- The curated catalog and generated `ai-discovered.yaml` remain separate.
  Pricing is updated only from reviewed, source-linked snapshots.

## Before the next release

1. Run `uv run pytest`.
2. Run `uv run ruff check most tests`.
3. Refresh dynamic provider inventory with
   `uv run python -m most catalog-refresh --show-models`.
4. Review [the AI provider guide](docs/ai-provider-guide.md) when provider
   models, prices, or e-INFRA routes change.
