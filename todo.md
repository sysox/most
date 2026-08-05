# most — implementation TODO for Codex

Context: `most` is a Python file-based safety kernel for multi-provider AI
access (CLI + API + browser routes, execution gate, journal, catalog).
This doc lists concrete gaps found against e-INFRA CZ / CERIT-SC AIaaS
docs, plus standardization items. Each item has enough detail to implement
without re-reading source docs. Source: docs.cerit.io/en/docs/ai-as-a-service/*

---

## 1. e-INFRA CZ as a provider — credential profile

**CORRECTION after re-reading current README: this is LARGELY ALREADY
IMPLEMENTED, not a gap.** Confirmed already present in most:
- `most credentials set einfra` (keyring storage)
- `most cerit-chat --model mini` (and other CERIT aliases)
- `most catalog-audit --provider einfra --show-models`
- e-INFRA already included in `./scripts/smoke-test-ai.sh` and the
  per-provider integration test pattern (`MOST_PROVIDER=claude` style)
- Aliases confirmed live: `mini`, `coder`, `agentic`, `kimi`, `glm`,
  `deepseek`

Only the narrower items below remain open.

### Facts
- OpenAI-compatible endpoint: `https://llm.ai.e-infra.cz/v1`
- Anthropic-compatible endpoint (for Claude Code specifically):
  `https://llm.ai.e-infra.cz/` (note: no `/v1`, Claude Code appends its own path)
- Auth env var used by most's own test harness: `CERIT_API_KEY`
- Cost: institutional, no per-token price. Treat as zero-cost in
  `pricing-update.yaml` / catalog pricing metadata (same convention already
  used for local/Ollama providers).
- Model names churn without notice ("usually at night, but possibly any
  time"); exact names are retired when replaced. **Only the alias set below
  is a stable contract.**

### Remaining implementation tasks
- [x] Confirm whether `thinker` and `deepseek-thinking` aliases exist in
  the current catalog — README only explicitly lists mini/coder/agentic/
  kimi/glm/deepseek. Add if missing (see alias table below).
- [x] Confirm whether reasoning-mode control (`chat_template_kwargs` for
  DeepSeek/GLM families, see below) is implemented in the `ai-chat`
  payload builder — unconfirmed either way, verify before assuming gap
  or assuming done.
- [x] Naming/duplication check: `cerit-chat --model mini` and
  `ai-chat --provider einfra` appear to be two separate entry points to
  the same provider. Confirm whether this is intentional (legacy alias
  command vs. generic unified command) or accidental duplication — pick
  one canonical path if it's the latter.
- [x] Confirm catalog entries mark maintained aliases vs
  `stability: volatile` for e-INFRA models — not confirmed present,
  low-cost to add if missing.

### Alias table — reference, cross-check against current ai-catalog.yaml
| Alias               | Resolves to (as of 2026-06-30) | Notes                          |
|----------------------|----------------------------------|----------------------------------|
| `mini`               | gpt-oss-120b                     | fast, general purpose — confirmed live |
| `coder`, `agentic`   | qwen3.5-122b                     | coding/agentic default — confirmed live |
| `thinker`            | deepseek-v4-flash-thinking        | reasoning forced on — not confirmed live |
| `kimi`               | kimi-k2.7                        | 1M context, multimodal, agentic — confirmed live |
| `glm`                | glm-5.2                          | strongest on Aider polyglot bench — confirmed live |
| `deepseek`           | deepseek-v4-flash                | reasoning off by default — confirmed live |
| `deepseek-thinking`  | deepseek-v4-flash-thinking        | reasoning forced on — not confirmed live |

### Reasoning mode control (model-specific quirk, needed for `ai-chat` payload builder)
- DeepSeek v4 family: reasoning **off** by default. Enable via
  `chat_template_kwargs: {"thinking": true}` in the request body, or use
  the `-thinking` alias variant to force it on regardless of flags.
- GLM 5.x family: reasoning **on** by default. Disable via
  `chat_template_kwargs: {"enable_thinking": false}`.
- Implement as a provider-specific request-body transform keyed off model
  family prefix (`deepseek-*` vs `glm-*`), not a global flag.
- Status: unconfirmed whether already implemented — verify before treating as a gap.

### Embedding models available (for future RAG work, not blocking)
`qwen3-embedding-4b` (2560-dim, 40960 ctx, multilingual), `qwen3-reranker-4b`,
`nomic-embed-text-v1.5`/`v2-moe` (768-dim, English), `mxbai-embed-large`,
`multilingual-e5-large-instruct`. Same endpoint, `/v1` embeddings path.
- [x] Add these as catalog entries under the `einfra` provider with
  `capability: embedding` — currently only listed as facts, no confirmed
  catalog entry exists for them yet.

### Modality command generalization — corrected status
Per current README: `ai-embed`, `ai-image`, `ai-image-analyze`, and
`ai-speech` are explicitly stated to "currently target the Google Gemini
API" — confirmed still Gemini-only, real gap.

**Correction: `ai-transcribe` is NOT Gemini-locked.** README shows
`ai-transcribe --provider openai --model whisper-1` — it already accepts
a `--provider` flag and is provider-generic. This means adding e-INFRA
Whisper support is much smaller than previously scoped:
- [x] Add `whisper-large-v3` (API-only, per e-INFRA docs) as an einfra
  catalog entry with `capability: transcription`. If the provider
  adapter is truly generic (as `--provider openai` suggests), this may
  be a catalog-only change — verify, don't assume code changes needed.
- [ ] `ai-embed` / `ai-image` / `ai-image-analyze` / `ai-speech`
  generalization to einfra remains real work — these have no `--provider`
  flag shown anywhere in current docs, confirmed Gemini-specific.
  Lower priority: e-INFRA's own image-generation API availability is
  still unconfirmed (WebUI has an "Image" toggle on chat models, unclear
  if it's a standalone API-callable endpoint) — verify before implementing.

---

## 2. Local file access — e-INFRA as backend for existing cli-chat wrappers

### CORRECTED understanding — sandbox mode is NOT uniform across wrappers
Earlier version of this doc assumed all `cli-chat` wrappers grant equal
file read/write access because the underlying binaries are agentic.
**Current README contradicts this for codex specifically:**

> "Codex runs with an ephemeral, read-only, non-repository execution."

This means `most cli-chat codex` today does **not** write to your actual
project files by default — it's sandboxed to a throwaway, read-only,
non-repo context. This is different from what CERIT's own docs show for
Claude Code (`~/.claude/settings.json` with `defaultMode: acceptEdits`,
which does allow writes) and from `agy`, which has its own permission
system (`/permissions` in an interactive session, explicit warning
against `--dangerously-skip-permissions`).

**Practical consequence: "local file access via cli-chat" is not one
capability, it's three different sandbox postures, one per wrapper.**
Before building anything further on top of this (tandem profiles,
pipelines), the actual current behavior must be audited and made
explicit — not assumed uniform.

### Implementation tasks — sandbox audit (do this FIRST, blocks correctness of everything else in this section)
- [x] Audit and document current write-access behavior for each
  `cli-chat` wrapper (claude / codex / agy) as most actually configures
  it today — not what upstream CLI defaults to, what most's own
  invocation sets.
- [x] If codex's ephemeral/read-only/non-repo mode is an intentional
  safety default (plausible — matches most's general cautious posture),
  expose an explicit opt-in for write-capable execution (e.g. a
  `--writable` flag or task-profile-level `write: true`) rather than
  leaving "local file access" as an implicit, wrapper-dependent
  assumption.
- [x] This directly affects tandem: a `coding` task profile that expects
  actual file edits must specify a wrapper/mode that is confirmed
  writable — defaulting to codex's current mode would silently produce
  no file changes and could be mistaken for a bug rather than a
  deliberate safety default.

### Facts
Claude Code, Codex, and OpenCode all work unmodified against e-INFRA by
pointing their own env vars at it. Whatever file access each CLI grants
(subject to the sandbox-mode correction above) is inherited from the CLI
itself — **no new tool-loop code needed in most**, only correct
plumbing of credentials/config plus the sandbox-mode audit above.

### Claude Code config (env vars)
```
export ANTHROPIC_BASE_URL="https://llm.ai.e-infra.cz/"
export ANTHROPIC_AUTH_TOKEN="sk-..."          # the e-INFRA API key
export ANTHROPIC_MODEL="agentic"
export ANTHROPIC_DEFAULT_OPUS_MODEL="thinker"
export ANTHROPIC_DEFAULT_SONNET_MODEL="agentic"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="mini"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
```
One-time onboarding quirk (Claude Code CLI, not most's problem, but worth
noting for install docs): first run needs `hasCompletedOnboarding: true`
manually added to `~/.claude.json` if login screen can't complete (no
Anthropic account when routed through e-INFRA).

### Codex config (env vars)
```
export OPENAI_BASE_URL=https://llm.ai.e-infra.cz
export OPENAI_API_KEY=sk-...
```
Invocation: `codex --model qwen3-coder-next --full-auto`. On first run,
select "Provide your own API key" / "Use your own OpenAI API key for
usage-based billing".

### OpenCode config (JSON file, not env vars)
`~/.config/opencode/opencode.json`:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LiteLLM",
      "options": { "baseURL": "https://llm.ai.e-infra.cz/v1" },
      "models": {
        "kimi-k2.6": {"name": "kimi-k2.6"},
        "gpt-oss-120b": {"name": "gpt-oss-120b"},
        "glm-5.1": {"name": "glm-5.1"},
        "qwen3.5": {"name": "qwen3.5"},
        "deepseek-v4-pro-thinking": {"name": "deepseek-v4-pro-thinking"}
      }
    }
  }
}
```
Inside opencode: `/connect` → select LiteLLM → paste API key → select model.
Known issue: `gpt-oss-120b` has partial support in OpenCode.

### Implementation tasks
- [x] `cli-chat claude --credential-provider einfra` / `cli-chat codex --credential-provider einfra`
  / `cli-chat opencode --provider einfra` — generate/export the above env
  vars (or write the opencode.json) from the stored e-INFRA credential
  before invoking the binary, rather than requiring the user to export
  them manually in their shell. This is the actual "local file access"
  deliverable — a config-generation step, not new sandboxing code.
  Note: existing wrappers already take an `--allow-unknown-connectivity`
  flag (confirmed for codex/claude/agy in current README) — the new
  einfra credential plumbing should follow the same flag/option
  conventions rather than inventing a new pattern.
- [ ] Add `opencode` as a fourth `cli-chat` target alongside
  claude/codex/agy (currently confirmed missing from most — README lists
  only claude/codex/agy).
- [x] Document/enforce: never export these env vars manually in a shell
  outside most — breaks journaling guarantee (see conversation decision:
  "always `most cli-chat`, never bare `claude`").
- [x] Security implementation detail: pass the API key to the child
  process via `subprocess`'s `env=` parameter directly, not by writing a
  literal `export ANTHROPIC_AUTH_TOKEN=sk-...` line to a shell — the
  latter exposes the key in that process's environment as visible via
  `ps eww`/`/proc/<pid>/environ` to other users on a shared machine.
  Relevant for the shared ThinkPad/Pi setups, not just the personal
  MacBook.

---

## 3. MCP servers — mechanism in most, selection stays in tandem

### Facts
Hosted MCP servers, base path `https://llm.ai.e-infra.cz/[name]/mcp`,
same bearer auth as the chat API. No MCP mechanism is mentioned anywhere
in most's current README — confirmed fully a gap, not partially done
like section 1 turned out to be.

Reusable existing infrastructure: most already has `provider-health.yaml`
and a `catalog-health` command tracking provider call failures generically.
The MCP attach mechanism doesn't need this directly, but if MCP server
attach ever fails (auth, unreachable), follow the same
record-and-report pattern already established for provider health rather
than inventing a separate error-tracking scheme.

| Server      | Purpose                                        |
|-------------|--------------------------------------------------|
| `ddg_search`| web search + page fetch (**required replacement** for Claude Code's native web_search/web_fetch, which silently fail through this proxy — Anthropic-API-only feature) |
| `DocFork`   | doc search across GitHub/web, returns markdown    |
| `npmjs`     | npm package metadata                              |
| `solver`    | symbolic math, stats, matrix ops                  |
| `prolog`    | Trealla Prolog query execution                    |
| `k8scerit`  | k8s manifest generation/validation for CERIT-SC   |
| `shadcn`    | shadcn/ui component reference                     |
| `tailwind`  | Tailwind component reference                      |

Attach command (Claude Code):
```
claude mcp add-json ddg_search '{"type":"http","scope":"user","url":"https://llm.ai.e-infra.cz/ddg_search/mcp","headers":{"Authorization":"Bearer BEARER"}}'
```

### Implementation tasks
- [ ] Verify first (don't assume): does `codex` or `opencode` support MCP
  server registration at all, and if so what's the equivalent of
  `claude mcp add-json`? Not confirmed in any doc read so far — only
  Claude Code's MCP attach command is documented. If codex/opencode lack
  MCP support, the mechanism below is Claude-Code-only for now, and that
  scope limit should be explicit rather than assumed away.
- [x] `most` implements the *mechanism*: given a list of MCP server names,
  run the `claude mcp add-json` calls (or equivalent registration for
  codex/opencode if confirmed above) before starting a cli-chat session
  routed through einfra.
- [x] Auto-include `ddg_search` by default whenever
  `provider=einfra AND cli=claude`, since native web tools are silently
  broken in that combination — this should not require the caller to
  remember it.
- [x] Do NOT hardcode which servers to attach beyond the ddg_search
  default above — the general list is a parameter supplied by the caller
  (tandem's task-profiles.yaml `mcp:` field), not decided inside most.
- [x] Warning in docs: don't attach all servers by default, each consumes
  context budget.

---

## 4. Exposure-policy / sensitivity tier rules

### Facts (from e-INFRA privacy policy)
- **WebUI**: uploaded files stored permanently, no user-facing delete.
  Chat history in Postgres, backed up to S3/CESNET with 30-day retention.
  Explicitly "not certified for protected data" per e-INFRA's own policy.
- **API route**: bypasses WebUI storage layer entirely, same on-prem
  inference engines. e-INFRA's own recommendation for sensitive workflows.
- Some models shown in WebUI are **not actually on-prem** — "truly
  external" passthroughs to third parties (example given: GPT-5) exist
  under special agreements. Data leaves e-INFRA infrastructure for these.

### Implementation tasks
- [x] Hard-block (not just warn) any `browser-chat`-style / WebUI-style
  route when the active session/workspace tier is `sensitive`. This is
  an addition to most's existing exposure-policy evaluator, same
  mechanism already used elsewhere — just add this rule.
  **Scope correction: this must apply to `browser-chat` for ALL
  providers** (`gemini`, `chatgpt`, `claude`, `cerit`), not just the
  e-INFRA WebUI. All four are the same capability class — text/image
  only, storage/logging outside most's control — so the sensitive-tier
  block must be a rule on the `browser-chat` route itself, not a
  per-provider special case for `cerit`.
- [ ] **Non-goal, write explicitly to prevent accidental scope creep:**
  voice/real-time-audio capture from a provider's web UI (e.g. ChatGPT
  Advanced Voice, Gemini Live) is NOT part of `browser-chat` and should
  not be implemented as a "small extension" of it. `browser-chat` is a
  text DOM relay (WebDriver or manual copy-paste); voice mode is a
  live audio stream requiring mic capture, TTS injection, and raw-audio
  journaling — a different capability class entirely. If voice is ever
  needed, it goes through the api route (`ai-speech`/`ai-transcribe`,
  already implemented, see section on modality commands below),
  not through browser automation.
- [x] Add an `is_external_passthrough: bool` field to catalog entries for
  e-INFRA-listed models; default `false`, must be explicitly confirmed
  `false` (i.e. verified on-prem) before a model is eligible for
  `sensitive`-tier task profiles. Until verified, treat unknown e-INFRA
  models as ineligible for sensitive tier.
- [ ] `catalog-audit` for the einfra provider should record whatever
  signal is available (e.g. cross-check against the documented "internal
  models" list) to help set this field, but manual confirmation is
  acceptable for now — don't over-engineer detection.

---

## 5. Journal extension (needed for tandem, implement in most)

- [x] Add optional fields to journal entry schema: `profile` (string),
  `pipeline_id` (string), `stage_index` (int). All optional/nullable —
  existing entries without them remain valid.
- [x] No new journal file/store — tandem writes into most's existing
  `application-data` journal using most's existing write path, just
  populating these new fields when applicable.

---

## 6. Standardization — adopt now

### JSON Schema validation
- [x] Write JSON Schema for `ai-catalog.yaml`; `task-profiles.yaml` remains
  owned by tandem.
  (the latter technically lives in tandem, but if most exposes a shared
  schema-validation utility, tandem can reuse it — decide based on
  whether most already has a schema/validation dependency).
- [x] Validate on load and on `catalog-audit --update` write-back, fail
  loudly rather than writing malformed YAML silently.

### OIDC / OAuth2 device-flow for e-INFRA credentials

**Status: confirmed OIDC provider exists, device-flow grant type NOT
confirmed. Research spike required before implementation — do not assume
device-flow works, verify first.**

Confirmed facts (from aai.cesnet.cz / e-INFRA AAI docs):
- e-INFRA CZ AAI is a full OIDC provider, login endpoint
  `https://login.e-infra.cz`. Members of Czech academic institutions
  authenticate with home-organization credentials through it.
- Service provider registration portal: `https://spadmin.e-infra.cz/` —
  a new OIDC client (relying party) must be registered here first,
  including a redirect URI, before any flow can be used.
- General OIDC RP implementation guide:
  `https://aai.cesnet.cz/en/index/documentation/sp/proxy/implementing_the_service_provider`
- Hands-on OIDC connection walkthrough (PDF):
  `https://aai.cesnet.cz/_media/en/index/documentation/sp/proxy/oidc_handson.pdf`

What's NOT confirmed and needs the research spike:
- [ ] Whether the `urn:ietf:params:oauth:grant-type:device_code` grant
  (RFC 8628, "device authorization flow") is enabled for this OIDC
  provider — being a standard OIDC provider does not guarantee every
  grant type is turned on. Check the provider's `.well-known/openid-configuration`
  (likely at `https://login.e-infra.cz/.well-known/openid-configuration`)
  for `grant_types_supported` and `device_authorization_endpoint`.
- [ ] Whether registering `most` as a service provider via spadmin.e-infra.cz
  is realistic for a personal CLI tool (this portal reads as intended for
  institutional services, not individual developer tools — may require
  contacting CERIT-SC/e-INFRA support, same contact used elsewhere in
  these docs: k8s@cerit-sc.cz).
- [ ] Whether the resulting OIDC access token is even usable as a bearer
  credential against `llm.ai.e-infra.cz` — the AIaaS API key (from
  chat.ai.e-infra.cz Settings > API keys) may be a *separate* credential
  system layered on top of AAI login, not directly interchangeable with
  a raw OIDC token. This is the biggest open question — if true, device-flow
  would only replace the *browser login step*, not eliminate the manual
  API-key-copy step, which would reduce the payoff significantly.

- [ ] After the spike: if device_authorization_endpoint exists AND the
  resulting token works against the AIaaS API, implement
  `most credentials set einfra` as a device-flow login.
- [ ] If not: keep manual key entry, close this item, don't block on it.
  The manual copy-paste is annoying but not broken — deprioritize rather
  than force a solution that doesn't fit the actual credential model.

### LiteLLM refactor (do opportunistically, not urgent)
- [ ] When next touching `ai-chat`'s provider client code, consider
  replacing the per-provider custom clients (openai, anthropic, gemini,
  einfra) with LiteLLM SDK calls. Not a standalone task — bundle with
  other api-route work.

---

## 7. Deferred — only implement if it becomes actual pain

- **W3C PROV / OpenLineage export of the journal** — only if journal
  needs to be citable/exportable outside most (e.g. thesis reproducibility
  appendix). No current requirement.
- **OpenTelemetry** — overkill for single-user CLI, skip unless most
  becomes a multi-service/distributed system, which is out of scope.
- **Codebase indexing / Qdrant integration** (mentioned in e-INFRA docs
  for Roo Code) — relevant only if most grows a codebase-search feature;
  not currently planned.

---

## Suggested implementation order for Codex

1. **Section 2 sandbox audit** (claude/codex/agy write-access modes) —
   do this first, it's a correctness check on an assumption everything
   else in section 2 depends on, and it's cheap (reading + testing
   existing behavior, not new code).
2. Section 1 remaining items (alias/reasoning-mode confirmation, einfra
   whisper catalog entry) — mostly verification + small catalog edits,
   not the large integration originally scoped; most of section 1 is
   already implemented.
3. Section 2 config-generation (cli-chat env/config plumbing for einfra)
   — the actual file-access deliverable, once sandbox audit confirms
   which wrappers are meaningfully writable.
4. Section 3 (ddg_search auto-attach, MCP mechanism) — confirmed fully
   a gap, depends on 1+2 for the einfra+claude combination it targets.
5. Section 4 (exposure-policy sensitive-tier rule, generalized to all
   browser-chat providers) — independent, can parallelize with anything.
6. Section 5 (journal fields) — small, unblocks tandem's first integration.
7. Section 6 (JSON Schema) — independent, cheap, do anytime.
8. Section 6 (OIDC device-flow) — needs research spike first, not pure implementation.
9. Section 6 (LiteLLM) — opportunistic, no deadline.
10. Section 7 — do not implement now.
