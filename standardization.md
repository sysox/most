# most — standardization recommendations

Scope: standards to adopt inside `most` (access layer). Boundary rule from
tandem/most split applies here too: anything about *how most talks to a
provider or CLI binary* belongs here. Anything about *which provider/model/
tool to pick for a task* stays out of most, belongs in tandem.

## Adopt now

### LiteLLM
Replaces: custom per-provider clients in the `api`/`ai-chat` route
(currently one hand-written client per provider — openai, anthropic,
gemini, einfra).
Change: internal implementation detail of `ai-chat`, not a new route, not
a new project. Tandem never touches this — it never talks to a provider
directly.
Payoff: adding a new api-route provider becomes config, not a new client
class. e-INFRA docs already recommend it for exactly this reason.
Status: refactor, not a missing feature — current custom clients work,
this just reduces future maintenance cost.

### MCP — mechanism only
Replaces: nothing broken today, but formalizes tool-attach for the `cli`
route (`claude mcp add-json ...` before invoking a wrapped CLI session).
Change: most owns *how* an MCP server gets attached to a cli-chat
invocation. Tandem owns *which* servers get attached per task profile
(`mcp: [ddg_search, DocFork, npmjs]` in task-profiles.yaml) — most just
executes that list at session start.
Rule: tandem never calls `claude mcp add-json` itself — same violation
class as tandem calling a provider directly.

Status: implemented for Claude through a session-scoped `--mcp-config` file.
The file contains no secret; the e-INFRA token is supplied through the child
process environment. Codex and OpenCode are not included until their current
CLI registration APIs are verified.

### OIDC / OAuth2 device-flow
Replaces: manual copy-paste of the e-INFRA API key out of the WebUI
Settings > Account > API keys screen into `most credentials set einfra`.
Change: e-INFRA CZ AAI already runs on Shibboleth/OIDC. `most credentials
set einfra` could trigger a device-flow login instead of requiring a
manual key copy.
Payoff: fewer manual steps, key never sits in shell history or clipboard.
Status: deferred after a completed research spike. The current e-INFRA API
documentation requires a separate API key generated in Open WebUI and does
not document an OIDC device-flow endpoint, token exchange, or an OIDC token
as an API credential. Keep the secure keyring flow until e-INFRA exposes a
supported device flow that issues an API-compatible credential. The OIDC
integration documented for other e-INFRA services requires pre-registration
and authorization-code callbacks, so it is not a safe assumption for MOST's
local CLI.

### JSON Schema
Replaces: no validation on `ai-catalog.yaml` / `task-profiles.yaml`
structure.
Change: schema-validate both files, catch malformed entries before a
runtime failure. Cheap to add since `catalog-audit --update` already
writes back to these files programmatically — a bad write is currently
silent until something calls it.
Status: implemented for `ai-catalog.yaml`; `task-profiles.yaml` remains owned
by tandem.

## Consider later — no current pain to justify it

### W3C PROV / OpenLineage
Would replace: most's own journal entry format in `application-data`.
Only worth it if the journal needs to be exportable/citable outside
most — e.g. as part of dissertation/publication reproducibility evidence.
Otherwise it's a standardization layer over something that already works
internally. Don't adopt speculatively — matches the "don't build ahead of
a concrete use case" rule already applied to tandem's pipeline primitive.

### OpenTelemetry
Would replace: execution-gate logging.
Overkill for a single-user CLI tool. OTel earns its complexity in
distributed/multi-service systems — most is neither. Skip.

## Priority order
1. Journal pipeline context fields — implemented.
2. JSON Schema validation on the MOST catalog — implemented.
3. LiteLLM refactor of the api route's provider clients — worthwhile but
   not urgent, do when next touching that code anyway.
4. MCP attach mechanism — implemented for Claude; extend only after another
   CLI exposes a verified registration API.
5. PROV/OpenLineage, OpenTelemetry — revisit only if a concrete need
   appears (e.g. journal needs external citation, or most stops being
   single-user/single-machine).
