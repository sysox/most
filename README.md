# most

Python file-based safety kernel for the multi-provider AI access application.

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

The `chat` command uses the local OpenAI-compatible endpoint at
`http://127.0.0.1:11434/v1` by default, so it works with Ollama without an API
key. Pass one prompt for a single turn or omit the prompt for an interactive
session:

```bash
uv run python -m most --data-root ./application-data chat --model granite4.1:3b "Hello"
uv run python -m most --data-root ./application-data chat --model ministral-3:8b
```

Browser communication is optional and uses Firefox with an isolated profile:

```bash
uv sync --extra browser
uv run python -m most --data-root ./application-data browser-chat gemini
uv run python -m most --data-root ./application-data browser-chat chatgpt
uv run python -m most --data-root ./application-data browser-chat claude
```

If a provider blocks WebDriver sign-in, use manual browser relay mode. MOST
opens the normal browser, and you copy the prompt and response yourself:

```bash
uv run python -m most --data-root ./application-data browser-chat gemini --manual
```

This mode does not inspect cookies, automate login, bypass CAPTCHA, or evade
provider security controls. It records the manually mediated exchange in the
MOST journal.

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
