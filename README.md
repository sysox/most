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
```

The current implementation starts with portable domain records, deterministic
result lineage, atomic YAML/JSON persistence, crash-tolerant JSONL recovery,
exposure-policy evaluation, and adapter boundaries. Workspace orchestration and
provider adapters are added behind these interfaces.
