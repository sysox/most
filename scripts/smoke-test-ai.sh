#!/usr/bin/env bash

# Live provider smoke test. This sends one short request to each configured API
# route and may incur provider charges. Override model names with MOST_*_MODEL.

set -u

prompt="${MOST_SMOKE_PROMPT:-Reply with exactly: MOST smoke test works}"
failures=0

run_test() {
    local label="$1"
    shift
    printf '\n[%s]\n' "$label"
    if "$@"; then
        printf 'PASS: %s\n' "$label"
    else
        printf 'FAIL: %s\n' "$label" >&2
        failures=$((failures + 1))
    fi
}

run_test "ollama/${MOST_OLLAMA_MODEL:-granite4.1:3b}" \
    uv run python -m most ai-chat --provider ollama --model "${MOST_OLLAMA_MODEL:-granite4.1:3b}" --no-refresh "$prompt"

run_test "einfra/${MOST_EINFRA_MODEL:-mini}" \
    uv run python -m most ai-chat --provider einfra --model "${MOST_EINFRA_MODEL:-mini}" --no-refresh "$prompt"

run_test "openai/${MOST_OPENAI_MODEL:-gpt-5.6}" \
    uv run python -m most ai-chat --provider openai --model "${MOST_OPENAI_MODEL:-gpt-5.6}" --no-refresh "$prompt"

run_test "anthropic/${MOST_ANTHROPIC_MODEL:-claude-sonnet-5}" \
    uv run python -m most ai-chat --provider anthropic --model "${MOST_ANTHROPIC_MODEL:-claude-sonnet-5}" --no-refresh "$prompt"

run_test "google/${MOST_GOOGLE_MODEL:-gemini-3.5-flash}" \
    uv run python -m most ai-chat --provider google --model "${MOST_GOOGLE_MODEL:-gemini-3.5-flash}" --no-refresh "$prompt"

if (( failures > 0 )); then
    printf '\n%d provider test(s) failed.\n' "$failures" >&2
    exit 1
fi

printf '\nAll provider smoke tests passed.\n'
