# MOST installation and provider setup

This guide installs MOST and the providers currently supported by this
workstation. Run all MOST commands from the repository directory. Each
provider is optional; install only the routes you intend to use.

## 1. Operating-system prerequisites

Supported development targets are 64-bit Linux, Windows 10/11, and macOS.
MOST requires Python 3.11 or newer, but `uv` can download and manage Python
for the project.

Install `uv` using the official instructions:

- Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Windows package manager: `winget install --id=astral-sh.uv -e`

Restart the terminal after installation and verify:

```text
uv --version
```

Official reference: <https://docs.astral.sh/uv/getting-started/installation/>.

## 2. Obtain and install MOST

Clone the repository, enter it, and synchronize the locked environment.

Linux/macOS:

```bash
git clone https://github.com/sysox/most.git
cd most
uv sync --extra dev
```

Windows PowerShell:

```powershell
git clone https://github.com/sysox/most.git
Set-Location most
uv sync --extra dev
```

The project environment is stored in `.venv`; activation is optional because
all examples use `uv run`.

Verify the installation:

```bash
uv run python -m most --help
uv run pytest
uv run ruff check most tests
```

PowerShell uses the same `uv run` commands.

## 3. Initialize MOST data

MOST stores sessions, executions, and journal records below the selected data
root. The default is `./application-data`; keep it outside version control.

```bash
uv run python -m most --data-root ./application-data create-session "Setup test"
uv run python -m most --data-root ./application-data list-sessions
```

Do not put API keys, browser profiles, or generated application data into the
Git repository.

## 4. Local Ollama setup

Install Ollama from <https://ollama.com/download>.

Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

On macOS or Windows, start the installed Ollama application. Then download
models appropriate for the machine:

```bash
ollama pull granite4.1:3b
ollama pull ministral-3:8b
ollama pull embeddinggemma:latest
ollama list
```

Test Ollama directly:

```bash
curl http://127.0.0.1:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"granite4.1:3b","messages":[{"role":"user","content":"Reply with exactly: Ollama works"}]}'
```

PowerShell equivalent:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/v1/chat/completions -Method Post `
  -ContentType 'application/json' `
  -Body '{"model":"granite4.1:3b","messages":[{"role":"user","content":"Reply with exactly: Ollama works"}]}'
```

Test through MOST:

```bash
uv run python -m most --data-root ./application-data \
  chat --model granite4.1:3b "Reply with exactly: MOST local works"
```

## 5. Cloud CLI providers

These routes use provider-installed CLI applications and their existing
subscription authentication. MOST does not need or store their login tokens.

### OpenAI Codex

Install Node.js 18+ if it is not already available, then:

```bash
npm install -g @openai/codex
codex --help
codex login
codex login status
```

Authenticate with the ChatGPT account that owns the subscription. Official
references: <https://help.openai.com/en/articles/11096431> and
<https://help.openai.com/en/articles/11381614>.

Test through MOST:

```bash
uv run python -m most --data-root ./application-data \
  cli-chat codex --allow-unknown-connectivity \
  "Reply with exactly: MOST GPT works"
```

### Anthropic Claude

Install from the official Claude Code instructions. The npm option is:

```bash
npm install -g @anthropic-ai/claude-code
claude --help
claude
```

Complete the browser login when Claude asks for it. Official reference:
<https://docs.anthropic.com/en/docs/claude-code/getting-started>.

Test through MOST:

```bash
uv run python -m most --data-root ./application-data \
  cli-chat claude --allow-unknown-connectivity \
  "Reply with exactly: MOST Claude works"
```

### Google Gemini through Antigravity (`agy`)

The Gemini CLI individual sign-in path may be retired or unavailable. Install
Antigravity CLI using its current official instructions:

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
agy --help
```

On Windows, use the installer instructions at
<https://antigravity.google/docs/cli-getting-started>. Start `agy`, complete
the Google/Antigravity login manually, and verify the account and model:

```bash
agy --help
agy models
```

Test through MOST:

```bash
uv run python -m most --data-root ./application-data \
  cli-chat agy --allow-unknown-connectivity \
  "Reply with exactly: MOST Gemini works"
```

If headless mode says a command permission is required, configure a narrow
allow rule in an interactive `agy --sandbox` session. Do not use
`--dangerously-skip-permissions` as a routine workaround.

## 6. API credentials and unified routes

API routes are separate from subscription-backed CLI logins. Store API keys in
the operating-system keyring:

```bash
uv run python -m most credentials set openai
uv run python -m most credentials set anthropic
uv run python -m most credentials set google
uv run python -m most credentials set einfra
uv run python -m most credentials list
```

The standard environment variables are `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, and `CERIT_API_KEY`. If one is already
exported, copy it into the keyring without printing it:

```bash
uv run python -m most credentials set openai --from-env
uv run python -m most credentials set anthropic --from-env
uv run python -m most credentials set google --from-env
uv run python -m most credentials set einfra --from-env
```

Test unified API routes with catalog models:

```bash
uv run python -m most ai-chat --provider openai --model gpt-5.6 "Hello"
uv run python -m most ai-chat --provider anthropic --model claude-sonnet-5 "Hello"
uv run python -m most ai-chat --provider google --model gemini-3.5-flash "Hello"
uv run python -m most ai-chat --provider einfra --model mini "Hello"
```

Use `--route api` to require an API route, or `--route cli` for a supported
subscription-backed CLI route. Never place keys in YAML, source files, shell
scripts, or committed documentation.

## 7. CERIT-SC / e-INFRA CZ setup

CERIT access requires an active MetaCentrum account or an eligible Masaryk
University account. Start at <https://chat.ai.e-infra.cz/> and complete the
e-INFRA CZ login. Access details:
<https://docs.cerit.io/en/docs/ai-as-a-service/chat-ai>.

Create the API key in Open WebUI:

1. Open Settings.
2. Open Account.
3. Open API keys.
4. Generate or display an API key. Do not use the JWT token.
5. Store the key in a password manager.

The API base URL is `https://llm.ai.e-infra.cz/v1`. Official API instructions:
<https://docs.cerit.io/en/docs/ai-as-a-service/ai-api>.

Set the key for the current shell without placing it in shell history.

Linux/macOS Bash or Zsh:

```bash
read -rsp "CERIT API key: " CERIT_API_KEY
export CERIT_API_KEY
echo
```

Windows PowerShell for the current terminal:

```powershell
$env:CERIT_API_KEY = Read-Host "CERIT API key"
```

For persistent storage, prefer the operating system password manager or a
secret-management tool. If `setx CERIT_API_KEY ...` is used on Windows, do not
put the key in a shared script or committed file; open a new terminal after
setting it. Environment variables are available to child processes, so MOST
reads the key only while the command is running.

Test the API directly:

```bash
curl https://llm.ai.e-infra.cz/v1/chat/completions \
  -H "Authorization: Bearer $CERIT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mini","messages":[{"role":"user","content":"Reply with exactly: CERIT works"}]}'
```

PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $env:CERIT_API_KEY" }
$body = @{ model = "mini"; messages = @(@{ role = "user"; content = "Reply with exactly: CERIT works" }) } | ConvertTo-Json -Depth 4
Invoke-RestMethod https://llm.ai.e-infra.cz/v1/chat/completions -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

Test through MOST:

```bash
uv run python -m most --data-root ./application-data \
  cerit-chat --model mini \
  "Reply with exactly: MOST CERIT works"
```

Use maintained aliases such as `mini`, `coder`, `agentic`, `kimi`, `glm`, and
`deepseek`. Query the live model list before using an exact model name because
CERIT may replace exact model versions.

## 8. Open WebUI browser route

For manual browser relay, no Selenium installation is required if the normal
browser can be opened by the operating system:

```bash
uv run python -m most --data-root ./application-data \
  browser-chat cerit --manual
```

Log in manually in the opened CERIT WebUI. Copy each prompt into the WebUI,
then paste the response into MOST and finish with `/done`. MOST journals the
prompt and pasted response. It does not read passwords, cookies, or bypass
CAPTCHA.

For Selenium-driven browser sessions, install the optional dependency:

```bash
uv sync --extra browser
```

Install Firefox and `geckodriver`, then verify:

```bash
firefox --version
geckodriver --version
```

Use separate named profiles for separate browser accounts:

```bash
uv run python -m most browser-chat gemini --profile gemini-edu
uv run python -m most browser-chat gemini --profile gemini-personal
uv run python -m most browser-chat claude --profile claude-work
```

Profiles keep cookies between runs, but Firefox still opens for each MOST
browser session. Login may be required again if cookies expire or the provider
requests verification.

On Windows, use the Firefox installer and place `geckodriver.exe` on `PATH`.
On macOS, install Firefox and use a signed `geckodriver` available on `PATH`.
On Linux, install Firefox and the distribution package or official release of
`geckodriver`. Manual relay is recommended when a provider blocks WebDriver
authentication.

## 9. Final verification checklist

Run these checks on every new machine:

```bash
uv run pytest
uv run ruff check most tests
uv run python -m most --help
uv run python -m most --data-root ./application-data list-sessions
uv run python -m most --data-root ./application-data list-configurations
uv run python -m most catalog-refresh --show-models
uv run python -m most catalog-health
./scripts/smoke-test-ai.sh
```

Then test only the providers that were configured. Confirm that a session ID
is printed and inspect one execution:

```bash
uv run python -m most --data-root ./application-data \
  inspect-execution <execution-id>
```

The local journal is under the selected data root. Never commit it, API keys,
provider profiles, or copied sensitive conversations.

## 10. Common problems

- `uv: command not found`: restart the terminal or add uv's install directory
  to `PATH`.
- Ollama connection refused: start the Ollama application or `ollama serve`.
- `missing CERIT API key`: export `CERIT_API_KEY` in the same terminal that
  runs MOST.
- CERIT returns unauthorized: create a new Open WebUI API key and confirm the
  account has MetaCentrum/e-INFRA access.
- Browser sign-in fails in Selenium: use `browser-chat ... --manual`; do not
  bypass CAPTCHA or provider login protections.
- CLI provider reports missing authentication: run that provider directly,
  complete its one-time login, and retry the MOST command.
