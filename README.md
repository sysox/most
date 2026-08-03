# most

Python file-based safety kernel for the multi-provider AI access application.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

Basic commands:

```bash
python -m most --data-root ./application-data create-session "Research"
python -m most --data-root ./application-data create-configuration "Local Ollama" --provider local/Ollama
```

The current implementation starts with portable domain records, deterministic
result lineage, atomic YAML/JSON persistence, crash-tolerant JSONL recovery,
exposure-policy evaluation, and adapter boundaries. Workspace orchestration and
provider adapters are added behind these interfaces.
