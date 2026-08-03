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
python -m most --data-root ./application-data create-session "Research"
python -m most --data-root ./application-data create-configuration "Local Ollama" --provider local/Ollama
python -m most --data-root ./application-data list-sessions
python -m most --data-root ./application-data list-configurations
python -m most --data-root ./application-data inspect-execution <execution-id>
python -m most --data-root ./application-data inspect-workspace <repository> --diff
python -m most --data-root ./application-data inspect-workspace <repository> --compatibility
python -m most --data-root ./application-data chat --model granite4.1:3b
```

The `chat` command uses the local OpenAI-compatible endpoint at
`http://127.0.0.1:11434/v1` by default, so it works with Ollama without an API
key. Pass one prompt for a single turn or omit the prompt for an interactive
session:

```bash
python -m most --data-root ./application-data chat --model granite4.1:3b "Hello"
python -m most --data-root ./application-data chat --model ministral-3:8b
```

The current implementation starts with portable domain records, deterministic
result lineage, atomic YAML/JSON persistence, crash-tolerant JSONL recovery,
exposure-policy evaluation, and adapter boundaries. Workspace orchestration and
provider adapters are added behind these interfaces.
