# most

Python file-based safety kernel for the multi-provider AI access application.

See the [practical usage manual](examples/basic-usage.md) for copy-paste
examples covering text, embeddings, images, speech, and model selection.

## Installation

For complete Linux, Windows, and macOS setup—including provider logins,
Ollama models, CERIT API keys, browser support, and verification—see
[install.md](install.md).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check most tests
```

Basic commands:

```bash
uv run python -m most --data-root ./application-data create-session "Research"
uv run python -m most --data-root ./application-data create-configuration "Local Ollama" --provider local/Ollama
uv run python -m most --data-root ./application-data list-sessions
uv run python -m most --data-root ./application-data list-configurations
uv run python -m most --data-root ./application-data inspect-execution <execution-id>
uv run python -m most --data-root ./application-data inspect-workspace <repository> --diff
uv run python -m most --data-root ./application-data inspect-workspace <repository> --compatibility
uv run python -m most --data-root ./application-data chat --model granite4.1:3b
```

See [ai-map.md](ai-map.md) for the current provider inventory, recommended
task routing, privacy boundaries, and example commands.

The versioned [AI provider catalog](ai-catalog.yaml) is the structured source
for provider routes, model aliases, availability, pricing metadata, and the
official pages used to refresh it. Exact cloud prices and live e-INFRA model
availability should be refreshed before cost-sensitive or reproducibility-
sensitive work.

`ai-catalog.yaml` is the stable curated baseline. `ai-discovered.yaml` is a
generated snapshot of dynamic provider models and should be refreshed regularly;
it is not the place for manually maintained pricing.

The live provider test is opt-in. Test all configured providers and fail if a
provider is unavailable or missing credentials:

```bash
MOST_RUN_PROVIDER_INTEGRATION=1 uv run pytest tests/test_all_providers.py
```

Test one installed provider instead:

```bash
MOST_RUN_PROVIDER_INTEGRATION=1 MOST_PROVIDER=claude \
  uv run pytest tests/test_all_providers.py
```

Audit the catalog routes and model discovery endpoints from the current
machine. Missing credentials are reported as `unknown`; they are not treated
as provider failures. Add `--update` only when you want confirmed model
statuses written back to `ai-catalog.yaml`:

```bash
uv run python -m most catalog-audit
uv run python -m most catalog-audit --update
```

The normal update keeps the catalog curated. To import every discovered API
model, use the explicit sync option:

```bash
uv run python -m most catalog-audit \
  --update --sync-models
```

Synced models receive availability and capability metadata, but pricing remains
`unknown` until a reviewed pricing update is applied.

For routine use, `catalog-audit` automatically writes dynamic discovery to
`ai-discovered.yaml`. This keeps rotating provider models separate from the
stable curated catalog while making them available to selection and display
tooling. Use `--no-discovered` to disable the generated snapshot.

The shorter refresh command is equivalent for daily use:

```bash
uv run python -m most catalog-refresh --show-models
```

When a unified API chat request fails, MOST records the failure in
`application-data/provider-health.yaml`, rechecks the provider inventory, and
prints replacement candidates without silently changing models. Recheck all
recorded failures manually with:

```bash
uv run python -m most catalog-health
```

This health check uses provider model discovery; it does not send an extra chat
probe or incur an additional model request.

It refreshes route/model availability and writes `ai-discovered.yaml`. The
snapshot includes conservative task hints such as `coding`, `reasoning`,
`semantic-search`, and `transcription`; these are heuristics, not benchmark
claims. Pricing remains a separate reviewed update.

To inspect exact e-INFRA model names, ranked with reasoning/pro variants and
newer-looking model versions first:

```bash
uv run python -m most catalog-audit --provider einfra --show-models
```

The ranking is only for readability; the provider’s live metadata remains the
source of truth for actual availability and model quality.

For a daily Linux refresh, run the command from the repository directory using
a service environment that securely provides API credentials:

```cron
0 3 * * * cd /home/sysox/Projects/most && /usr/bin/uv run python -m most catalog-refresh
```

Pricing is refreshed separately and only from reviewed provider sources. The
checked-in [pricing-update.yaml](pricing-update.yaml) is the current example
snapshot; validate it before applying future changes.

Pricing is maintained separately from availability. Create a reviewed update
file using this format:

```yaml
prices:
  - provider_id: openai
    model_id: gpt-5.6-sol
    per_1m_tokens:
      input: 5
      output: 30
      cached_input: 0.5
    source:
      url: https://developers.openai.com/api/docs/pricing
      checked_at: 2026-08-04
```

Validate first, then explicitly write the update:

```bash
uv run python -m most catalog-pricing --source pricing-update.yaml
uv run python -m most catalog-pricing --source pricing-update.yaml --update
```

Prices must have an HTTPS source and review date. Unknown pricing remains
`unknown`; local providers are zero-cost and institutional services do not
claim a per-token user price.

OpenAI GPT is available through the official Responses API. Set the key only in
the process environment; it is not written to MOST configuration or payloads:

```bash
read -rsp "OpenAI API key: " OPENAI_API_KEY; export OPENAI_API_KEY; echo
uv run python -m most --data-root ./application-data gpt-chat \
  --model gpt-5.6 "Hello from MOST"
```

Use `--api-key-env` to select a different environment variable and `--base-url`
for a compatible gateway. The default endpoint is `https://api.openai.com/v1`.

API keys can also be stored in the native OS credential store through the
unified keyring backend:

```bash
uv run python -m most credentials set openai
uv run python -m most credentials set einfra
uv run python -m most credentials list
```

If a key is already exported, copy it without displaying it:

```bash
uv run python -m most credentials set openai --from-env
```

MOST uses environment variables first and the keyring second. `keyring` maps to
Secret Service on Linux, Keychain on macOS, and Credential Locker on Windows.
Remove a stored key with `most credentials remove <provider>`.

The unified API chat supports OpenAI, CERIT/e-INFRA, Anthropic, and Gemini:

```bash
uv run python -m most ai-chat --provider anthropic --model claude-sonnet-5 --route api "Hello"
uv run python -m most ai-chat --provider google --model gemini-3.5-flash --route api "Hello"
```

Use `--route cli` for subscription-backed local clients such as `claude` or
`agy`. Use `catalog-audit --show-models` to refresh the live model inventory.

Gemini for Education is recorded as a Google account profile rather than as a
separate API model. It requires an institution-managed Google Workspace for
Education account and is used through the Gemini web app or browser route:

```bash
uv run python -m most --data-root ./application-data browser-chat gemini
```

Google documents Education core-service protections including no human review
and no use of data to train models. Confirm the applicable Workspace edition
and administrator settings before sending institutional or student data.

Filter the catalog by modality:

```bash
uv run python -m most catalog-options --capability chat
uv run python -m most catalog-options --capability embedding
uv run python -m most catalog-options --capability image
uv run python -m most catalog-options --capability speech
```

`catalog-options` displays explicit `input` and `output` columns. For example,
an embedding model is `text -> embedding`, a Whisper model is `audio -> text`,
and an image generator is `text -> image`.

`ai-chat` requires the selected model to advertise the `chat` capability, so
embedding, image, and speech models cannot be sent accidentally to a text-chat
route.

Google Gemini capability-specific operations are available through the same
catalog and keyring:

```bash
uv run python -m most ai-embed --model models/gemini-embedding-001 --input document.txt --output document.embedding.json
uv run python -m most ai-image --model models/gemini-3-pro-image-preview --output picture.bin "Create a mountain illustration"
uv run python -m most ai-speech --model models/gemini-2.5-pro-preview-tts --output speech.bin "Read this sentence aloud"
uv run python -m most ai-image-analyze --model gemini-3.5-flash --input picture.png "Describe this image"
```

These commands currently target the Google Gemini API. The catalog validates
the required capability before sending a request; generated binary output is
written exactly as returned by the provider, with its MIME type printed.

The live test uses already authenticated local CLIs for Claude, Codex, Gemini,
and Antigravity. e-INFRA uses its OpenAI-compatible API route and therefore
requires `CERIT_API_KEY`; Ollama uses its local endpoint and needs no key.

The `chat` command uses the local OpenAI-compatible endpoint at
`http://127.0.0.1:11434/v1` by default, so it works with Ollama without an API
key. Pass one prompt for a single turn or omit the prompt for an interactive
session:

```bash
uv run python -m most --data-root ./application-data chat --model granite4.1:3b "Hello"
uv run python -m most --data-root ./application-data chat --model ministral-3:8b
```

CERIT-SC/e-INFRA CZ provides an OpenAI-compatible on-premise endpoint at
`https://llm.ai.e-infra.cz/v1`. Create an API key in the CERIT Open WebUI,
then provide it through the environment; MOST does not persist the key:

```bash
read -rsp "CERIT API key: " CERIT_API_KEY; export CERIT_API_KEY; echo
uv run python -m most --data-root ./application-data cerit-chat \
  --model mini "Hello from MOST"
```

Use maintained CERIT aliases such as `mini`, `coder`, `agentic`, `kimi`,
`glm`, or `deepseek`; exact model names may change. The request and response
are recorded in MOST's local journal. Access requires an active MetaCentrum
or eligible Masaryk University account. See the
[CERIT API documentation](https://docs.cerit.io/en/docs/ai-as-a-service/ai-api).

Browser communication is optional and uses Firefox with an isolated profile:

```bash
uv sync --extra browser
uv run python -m most --data-root ./application-data browser-chat gemini
uv run python -m most --data-root ./application-data browser-chat chatgpt
uv run python -m most --data-root ./application-data browser-chat claude
uv run python -m most --data-root ./application-data browser-chat cerit --manual
```

If a provider blocks WebDriver sign-in, use manual browser relay mode. MOST
opens the normal browser, and you copy the prompt and response yourself:

```bash
uv run python -m most --data-root ./application-data browser-chat gemini --manual
```

This mode does not inspect cookies, automate login, bypass CAPTCHA, or evade
provider security controls. It records the manually mediated exchange in the
MOST journal.

Use separate named profiles when you have more than one account, for example
personal Gemini and Gemini for Education. Each profile keeps its own login:

```bash
uv run python -m most browser-chat gemini --profile gemini-personal
uv run python -m most browser-chat gemini --profile gemini-edu
```

Installed subscription-backed CLI clients can be used directly from the
terminal. MOST runs them in an application-managed sandbox and records their
observable command/output history:

```bash
uv run python -m most --data-root ./application-data cli-chat codex --allow-unknown-connectivity
uv run python -m most --data-root ./application-data cli-chat claude --allow-unknown-connectivity
uv run python -m most --data-root ./application-data cli-chat agy --allow-unknown-connectivity
```

Codex runs with an ephemeral, read-only, non-repository execution. The
provider CLI itself handles subscription authentication; MOST never receives
or stores the provider login token.

`agy` is the Antigravity CLI replacement for the retired Gemini individual
sign-in flow. It runs with its own sandbox flag and uses the Google account
authentication established by Antigravity. Authenticate with `agy` once before
using it through MOST. If headless mode reports that a command permission is
required, open `/permissions` in an interactive `agy --sandbox` session and
add only the specific read-only command requested by Antigravity. Do not use
`--dangerously-skip-permissions` as a general solution.

For Snap-packaged Firefox on Linux, use a visible profile root if Firefox
cannot access the default hidden application-data path:

```bash
export MOST_BROWSER_PROFILE_ROOT="$HOME/most-browser-profiles"
mkdir -p "$MOST_BROWSER_PROFILE_ROOT"
```

The command opens the provider site, pauses for manual login, and then records
the conversation and execution in the same file-backed journal. It does not
bypass login, CAPTCHA, consent, rate limits, or other site controls.

The current implementation starts with portable domain records, deterministic
result lineage, atomic YAML/JSON persistence, crash-tolerant JSONL recovery,
exposure-policy evaluation, and adapter boundaries. Workspace orchestration and
provider adapters are added behind these interfaces.
