# MOST practical usage

These examples use the catalog, keeping model names and routes explicit. Run
`catalog-refresh` first when provider inventories may have changed.

## 1. See available capabilities

```bash
uv run python -m most catalog-refresh --show-models
uv run python -m most catalog-options --capability chat
uv run python -m most catalog-options --capability embedding
uv run python -m most catalog-options --capability image
uv run python -m most catalog-options --capability speech
```

Typical input/output mappings are:

```text
text -> text          ordinary chat or coding
text,image -> text    image understanding
text -> embedding     search/RAG vector
text -> image         image generation
text -> audio         speech synthesis
audio -> text         transcription, for example Whisper
```

## 2. Chat with a local model

```bash
uv run python -m most ai-chat \
  --provider ollama --model granite4.1:3b \
  "Summarize the idea of a database in one sentence."
```

## 3. Select a cloud provider and route

```bash
uv run python -m most ai-chat \
  --provider anthropic --model claude-sonnet-5 --route api \
  "Review this function for a possible bug."

uv run python -m most ai-chat \
  --provider google --model gemini-3.5-flash --route api \
  "Give me three names for this project."
```

Use `--route auto` (the default) to let MOST select an available route.

## 4. Use a subscription-backed CLI

```bash
uv run python -m most cli-chat claude --allow-unknown-connectivity "Explain this error."
uv run python -m most cli-chat agy --allow-unknown-connectivity "Suggest a simpler implementation."
```

These use authentication configured in the installed CLI; MOST does not need
the CLI subscription token.

## 5. Create an embedding from a text file

```bash
uv run python -m most ai-embed \
  --provider google --model models/gemini-embedding-001 \
  --input examples/sample.txt --output /tmp/sample.embedding.json
```

The output is JSON containing the model, vector dimensions, and values.
Embeddings are for semantic search and RAG, not chat responses.

## 6. Generate an image

```bash
uv run python -m most ai-image \
  --provider google --model models/gemini-3-pro-image-preview \
  --output /tmp/most-example-image.bin \
  "A clean blue geometric logo for a command-line AI tool"
```

The command prints the returned MIME type. Image-generation models are not
valid `ai-chat` models.

## 7. Generate speech

```bash
uv run python -m most ai-speech \
  --provider google --model models/gemini-2.5-pro-preview-tts \
  --output /tmp/most-example-speech.bin \
  "Welcome to the MOST practical example."
```

This is text-to-speech. Whisper has the opposite direction: audio input and
text output.

For OpenAI Whisper transcription:

```bash
uv run python -m most ai-transcribe \
  --provider openai --model whisper-1 \
  --input examples/media/sample-speech.wav
```

The transcription is printed and recorded in the session journal.

Refresh provider inventories and recheck models after a failed unified chat:

```bash
uv run python -m most catalog-refresh --show-models
uv run python -m most catalog-health
```

The same transcription and embedding interfaces can use an OpenAI-compatible
local or institutional endpoint when the selected catalog model advertises the
required modality, for example:

```bash
uv run python -m most ai-embed \
  --provider ollama --model embeddinggemma:latest \
  --input examples/sample.txt --output /tmp/local.embedding.json
```

Task records include provider usage when returned and estimate cost from the
catalog pricing metadata when both are available.

## 8. Analyze an image

```bash
uv run python -m most ai-image-analyze \
  --provider google --model gemini-3.5-flash \
  --input examples/media/sample-public-domain.jpg \
  "Describe the important objects and colors."
```

MOST rejects this request if the selected model does not advertise `image`
input. The same protection prevents sending an embedding model to `ai-chat`.

## 9. Inspect a recorded session

Every successful chat prints a session ID. Inspect an execution with:

```bash
uv run python -m most inspect-execution EXECUTION_ID
uv run python -m most list-sessions
```

## 10. Keep separate browser accounts

Browser profiles are available for Gemini, ChatGPT, Claude, and CERIT. Create
one named profile per account; each profile keeps its own login cookies:

```bash
uv run python -m most browser-chat gemini --profile gemini-edu
uv run python -m most browser-chat gemini --profile gemini-personal
uv run python -m most browser-chat claude --profile claude-work
uv run python -m most browser-chat chatgpt --profile chatgpt-personal
uv run python -m most browser-chat cerit --profile cerit-institution
```

Log into each profile once when Firefox opens. API and CLI routes use their own
credential systems and do not need browser profiles.

## 11. Store credentials safely

```bash
uv run python -m most credentials set openai
uv run python -m most credentials set anthropic
uv run python -m most credentials set google
uv run python -m most credentials set einfra
```

If a standard environment variable is already set, copy it without displaying
the secret:

```bash
uv run python -m most credentials set google --from-env
```

Keys are stored in the operating system keyring, not in the catalog.
