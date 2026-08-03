# Multi-Provider AI Access Application

**Specification version:** 7

## 1. Project Goal

The goal is to create a lightweight, cross-platform application for communicating with arbitrary AI systems through arbitrary supported methods.

The application must run on:

- macOS;
- Linux;
- Windows.

Supported AI access methods may include:

- official provider APIs;
- OpenAI-compatible APIs;
- local runtimes;
- browser-based AI services;
- command-line AI agents;
- custom adapters.

A model running on another private machine is not a separate adapter category by itself. It is represented by the normal protocol adapter, such as `OpenAICompatibleAdapter`, together with a remote endpoint and location metadata.

The user explicitly selects:

- the AI provider;
- the model;
- the access method;
- the credentials or browser profile;
- the workspace or files, when applicable;
- the logging and privacy policy.

The application must not hide meaningful differences between providers or access methods.

The central principle is:

> Select the AI, select how it is accessed, preserve every result, and use Git whenever AI changes versioned files.

This version is intended to be implementation-ready for the MVP.

---

## 2. Main Operating Modes

The application has two primary operating modes.

## 2.1 Communication Mode

Communication Mode is used for ordinary interaction with an AI.

Examples:

- asking questions;
- document analysis;
- brainstorming;
- summarization;
- generating plans;
- comparing models;
- requesting several revisions of an answer;
- tool-assisted research that does not modify a source workspace.

Every meaningful intermediate result must be preserved.

This includes:

- the original user input;
- effective system and application instructions;
- attachments and their hashes;
- every AI response;
- every revised AI response;
- tool calls and tool results;
- model-switching events;
- user corrections;
- intermediate plans;
- generated files;
- errors and retries;
- the final selected result.

Communication Mode does not require a source-code repository.

Its primary storage is a transparent file-based journal using:

```text
YAML       metadata and configuration snapshots
JSON       normalized requests and responses
JSONL      append-only events and streaming records
Markdown   readable conversation and intermediate outputs
Files      attachments and generated artifacts
```

The communication journal may optionally be placed under Git version control.

---

## 2.2 Workspace Mode

Workspace Mode is used when an AI reads, creates, edits, deletes, or reorganizes files iteratively.

Examples:

- modifying application source code;
- updating Markdown documentation;
- revising teaching materials;
- generating and refining configuration files;
- editing scripts;
- changing a project over several AI iterations;
- reviewing and correcting another AI's changes.

Git is required for Workspace Mode.

The AI must work in:

- an existing Git repository; or
- a newly initialized Git repository created for the workspace.

The preferred workflow uses:

- a dedicated branch;
- optionally a dedicated Git worktree;
- one checkpoint per meaningful AI iteration;
- complete communication logs linked to each checkpoint;
- explicit user approval before merging or finalizing changes.

The application must preserve both:

1. the communication with the AI; and
2. the exact file state produced by each iteration.

---

## 3. Development Philosophy

The first version should prioritize:

- fast implementation;
- minimal dependencies;
- readable files;
- Git-friendly history;
- easy manual inspection;
- easy AI-assisted improvement;
- replaceable persistence interfaces;
- no SQL database;
- no ORM;
- no database migrations.

The application itself should later be usable to improve its own source code through Workspace Mode.

---

## 4. Example AI Configurations

```text
Gemini Browser
Provider: Google
Model: selected in browser
Access method: browser automation
Authentication: dedicated browser profile
Use for: interactive analysis

Gemini API
Provider: Google
Model: configured API model
Access method: official API
Authentication: API key
Use for: automated processing

Claude Code
Provider: Anthropic
Access method: CLI
Authentication: subscription login
Workspace access: selected repository
Use for: iterative file and code changes

OpenAI API
Provider: OpenAI
Access method: official API
Authentication: API key
Use for: structured outputs and tools

Local Qwen
Provider: local/Ollama
Access method: OpenAI-compatible API
Endpoint: http://localhost:11434/v1
Location: local
Use for: private and offline work

Remote Ollama
Provider: local/Ollama
Access method: OpenAI-compatible API
Endpoint: http://private-host:11434/v1
Location: remote-private
Network: Tailscale
Use for: private workloads requiring another machine
```

The same provider may have several separate configurations because browser, API, CLI, and local access may expose different models and features.

---

## 5. High-Level Architecture

```text
+------------------------------------------------------+
|                    User Interfaces                   |
| Desktop UI | Web UI | CLI | REST API | Python SDK   |
+---------------------------+--------------------------+
                            |
                            v
+------------------------------------------------------+
|                    Application Core                  |
| Config | Sessions | Executions | Journal | Workspace |
+---------------------------+--------------------------+
                            |
                            v
+------------------------------------------------------+
|                    Adapter Registry                  |
| Native API | OpenAI-compatible | Browser | CLI       |
| Local Runtime | Custom                              |
+---------------------------+--------------------------+
                            |
                            v
+------------------------------------------------------+
|                       AI Systems                     |
| Cloud AI | Local AI | Remote AI | Browser AI | CLI   |
+------------------------------------------------------+
```

The application core understands:

- AI configurations;
- sessions and conversations;
- requests and responses;
- intermediate results;
- executions and execution steps;
- artifacts;
- workspaces;
- Git checkpoints;
- audit records.

Adapters understand:

- provider APIs;
- browser interfaces;
- CLI commands;
- local runtimes;
- remote endpoints;
- provider-specific functionality.

---

## 6. Cross-Platform Design

Business logic must remain independent of macOS, Linux, and Windows APIs.

Operating-system-specific behavior is isolated behind:

```text
PlatformServices
├── SecretStore
├── PathService
├── ProcessService
├── BrowserProfileService
├── FilePermissionService
├── NotificationService
└── ApplicationDataService
```

Suggested secret-store implementations:

```text
MacOSKeychainSecretStore
LinuxSecretServiceStore
WindowsCredentialManagerStore
EncryptedFileSecretStore
```

Suggested application data locations:

```text
macOS:
~/Library/Application Support/<ApplicationName>/

Linux:
$XDG_DATA_HOME/<application-name>/
or ~/.local/share/<application-name>/

Windows:
%LOCALAPPDATA%\<ApplicationName>\
```

All path and process handling must use platform-neutral abstractions.

---

## 7. Main Domain Classes

## 7.1 AIProvider

```text
AIProvider
- id
- name
- description
- website
- provider_type
- metadata
```

## 7.2 AIModel

```text
AIModel
- id
- provider_id
- model_name
- display_name
- version
- context_limit
- metadata
```

## 7.3 AIConfiguration

The central user-selectable AI setup.

```text
AIConfiguration
- id
- name
- provider_id
- model_reference
- access_method_id
- credential_reference
- location
- network
- privacy_policy
- logging_policy
- usage_notes
- enabled
- adapter_options
- declared_capabilities
- discovered_capabilities_reference
- user_capability_restrictions
```

`location` describes where execution occurs:

```text
local
remote-private
remote-public
provider-cloud
browser-session
```

`network` describes how the configured endpoint is reached, when relevant:

```text
localhost
local-network
Tailscale
VPN
public-internet
SSH-tunnel
custom
```

`network` is optional where connectivity is implicit, but it should be recorded for remote private endpoints and other nontrivial network paths.

Protocol details such as base URL, headers, certificates, and timeouts remain inside `adapter_options`.

## 7.4 AccessMethod

```text
AccessMethod
- id
- type
- adapter_type
- display_name
- configuration_schema
- supported_features
```

## 7.5 CredentialReference

```text
CredentialReference
- id
- credential_type
- storage_backend
- storage_key
- display_name
- created_at
- updated_at
```

The plaintext secret must never be written to YAML, JSON, Markdown, JSONL, or Git.

## 7.6 ExposureTransitionPolicy

Controls how differences between declared and resolved execution location or network are handled.

```text
ExposureTransitionPolicy
- default_action
- allowed_transitions
- confirmation_required_transitions
- forbidden_transitions
```

Possible actions:

```text
FAIL
REQUIRE_CONFIRMATION
ALLOW_BY_POLICY
```

A transition rule identifies both the declared and resolved trust state.

Example:

```yaml
default_action: FAIL

allowed_transitions:
  - from:
      location: local
      network: localhost
    to:
      location: local
      network: localhost

confirmation_required_transitions:
  - from:
      location: remote-private
      network: Tailscale
    to:
      location: remote-public
      network: public-internet
```

Absence of a matching rule must not be interpreted as permission.

## 7.7 LoggingPolicy

```text
LoggingPolicy
- log_user_inputs
- log_ai_outputs
- log_intermediate_results
- log_stream_events
- log_tool_calls
- log_raw_provider_response
- log_attachments
- log_file_changes
- redact_secrets
- redact_personal_data
- retention_days
- git_journal_enabled
```

---

## 8. Session and Result Model

## 8.1 AISession

An `AISession` is a logical sequence of interactions around one task or conversation.

```text
AISession
- id
- title
- mode
- created_at
- updated_at
- default_configuration_id
- workspace_id
- status
- metadata
```

Possible MVP modes:

```text
COMMUNICATION
WORKSPACE
```

`COMPARISON` is intentionally excluded from the MVP domain model. A later comparison feature may model one comparison session as several sibling interactions, each using a different `AIConfiguration`, linked by a `comparison_group_id`.

## 8.2 Interaction

An `Interaction` is one user or application request and the resulting AI activity.

```text
Interaction
- id
- session_id
- sequence_number
- configuration_id
- request_id
- execution_id
- created_at
- status
```

## 8.3 IntermediateResult

Every meaningful AI-produced state must be stored as an `IntermediateResult`.

```text
IntermediateResult
- id
- session_id
- interaction_id
- execution_id
- sequence_number
- result_type
- created_at
- content_reference
- structured_reference
- parent_result_id
- selected_as_final
- metadata
```

Result types may include:

```text
plan
draft
partial_answer
revised_answer
tool_assisted_answer
review
critique
summary
patch_proposal
file_revision
test_result
final_answer
error_recovery
```

`parent_result_id` allows revisions and branches to form a result tree rather than a flat list.

## 8.4 FinalResult

A final result is not a separate storage format. It is an `IntermediateResult` marked as selected.

This permits the user to later select a different intermediate version as the preferred result.

---

## 9. Request and Response Model

## 9.1 AIRequest

```text
AIRequest
- id
- session_id
- interaction_id
- configuration_id
- messages
- attachments
- generation_options
- provider_options
- execution_options
- created_at
```

## 9.2 Message

```text
Message
- id
- role
- content_parts
- created_at
- metadata
```

Roles may include:

```text
system
developer
user
assistant
tool
custom
```

## 9.3 ContentPart

```text
ContentPart
├── TextPart
├── ImagePart
├── AudioPart
├── VideoPart
├── FilePart
├── ToolResultPart
└── ProviderSpecificPart
```

## 9.4 AIResponse

```text
AIResponse
- id
- request_id
- configuration_id
- content_parts
- finish_status
- usage
- cost
- provider_metadata
- raw_response_reference
- created_at
```

An execution may create multiple `AIResponse` or `IntermediateResult` objects before completion.

---

## 10. Execution Model

An `Execution` is one invocation of one `AIConfiguration`.

It may contain several internal steps and produce multiple intermediate results.

```text
Execution
- id
- session_id
- interaction_id
- request_id
- configuration_id
- configuration_snapshot
- adapter_type
- state
- platform
- host_identifier
- resolved_location
- resolved_network
- started_at
- finished_at
- usage
- cost
- error
- provider_execution_reference
- diagnostic_references
```

Execution states:

```text
created
validating
ready
starting
running
streaming
waiting_for_user
completed
cancelled
failed
```

## 10.1 ExecutionStep

```text
ExecutionStep
- id
- execution_id
- sequence_number
- step_type
- status
- started_at
- finished_at
- input_reference
- output_reference
- intermediate_result_id
- metadata
```

Step types:

```text
model_generation
tool_call
tool_result
command_execution
file_change
user_confirmation
browser_action
review
test_execution
git_checkpoint
```

## 10.2 StreamEvent

```text
TextDeltaEvent
StatusEvent
ToolCallEvent
ToolResultEvent
FileEvent
UsageEvent
IntermediateResultEvent
CompletedEvent
ErrorEvent
```

Raw text deltas may be stored in `events.jsonl`, while meaningful assembled stages are stored as separate intermediate results.

---

## 11. Capability Model

Use:

```text
DeclaredCapabilities
DiscoveredCapabilities
UserCapabilityRestrictions
EffectiveCapabilities
```

`EffectiveCapabilities` are computed for the selected configuration and used for request validation.

Capabilities may include:

```text
text_input
text_output
streaming
file_upload
image_input
structured_output
tool_calling
web_search
workspace_access
filesystem_read
filesystem_write
repository_access
local_execution
```

---

## 12. Adapter Contract

Every adapter implements:

```text
validate_configuration(configuration)
test_connection(configuration)
get_capabilities(configuration)
list_models(configuration)
execute(request)
stream(request)
cancel(execution_id)
```

Optional functions:

```text
validate_request(request, configuration)
create_provider_conversation()
continue_provider_conversation()
upload_file()
delete_uploaded_file()
retrieve_usage()
retrieve_cost()
health_check()
```

`validate_configuration()` checks the configuration itself.

`ExecutionManager.validate_request()` checks whether the concrete request fits the selected configuration.

Before execution, the adapter must resolve the actual endpoint, location, and network path as far as reasonably determinable and return these values to `ExecutionManager`. The adapter must not suppress or silently downgrade a mismatch. Exposure-policy evaluation belongs to `ExecutionManager`.

---

## 13. Main Adapter Types

```text
OfficialAPIAdapter
OpenAICompatibleAdapter
BrowserAdapter
CLIAdapter
LocalRuntimeAdapter
CustomAdapter
```

Examples:

```text
OpenAIAPIAdapter
GeminiAPIAdapter
AnthropicAPIAdapter

GeminiBrowserAdapter
ClaudeBrowserAdapter
ChatGPTBrowserAdapter

ClaudeCodeAdapter
CodexCLIAdapter
GeminiCLIAdapter

OllamaLocalAdapter
MLXLocalAdapter
LlamaCppLocalAdapter
```

A remote private model normally uses the same protocol adapter as a local model:

```text
OpenAICompatibleAdapter
- endpoint: http://localhost:11434/v1
- location: local

OpenAICompatibleAdapter
- endpoint: http://private-host:11434/v1
- location: remote-private
- network: Tailscale
```

`LocalRuntimeAdapter` is reserved for lifecycle operations that are truly local, such as starting a local process, discovering installed models, or reporting local hardware state.

For remote endpoints, `location` and `network` are first-class `AIConfiguration` fields. The adapter remains selected by protocol, not by physical location.

---

## 14. Core Services

## 14.1 ConfigurationService

```text
create_configuration()
update_configuration()
delete_configuration()
duplicate_configuration()
validate_configuration()
test_configuration()
list_configurations()
refresh_capabilities()
```

## 14.2 AdapterRegistry

```text
register_adapter()
get_adapter_for_configuration()
list_adapter_types()
get_configuration_schema()
```

## 14.3 CapabilityResolver

```text
discover_capabilities()
invalidate_capability_snapshot()
compute_effective_capabilities()
```

## 14.4 SessionService

```text
create_session()
get_session()
list_sessions()
append_interaction()
branch_from_result()
select_final_result()
export_session()
```

## 14.5 ExecutionManager

```text
prepare_execution()
validate_request()
execute()
stream()
cancel()
retry()
recreate_request_with_configuration()
```

`recreate_request_with_configuration()` is the final name of the earlier `repeat_with_configuration()` concept. There is only one operation: it creates a new request and execution from a safe snapshot while excluding prior side effects.


Before transmitting prompts, attachments, credentials, or workspace content, `ExecutionManager` must compare the configuration's declared `location` and `network` with the adapter's resolved values.

If the resolved values differ in a way that increases exposure or crosses a trust boundary, execution must not continue silently.

Examples include:

```text
local           → remote-private
remote-private  → remote-public
private network → public internet
localhost       → non-local endpoint
VPN/Tailscale   → direct public connection
```

The applicable `ExposureTransitionPolicy` must produce one of these outcomes:

```text
FAIL
    Reject the execution before transmission.

REQUIRE_CONFIRMATION
    Display the declared and resolved values, explain the increased exposure,
    and require explicit approval for this execution.

ALLOW_BY_POLICY
    Continue only when an explicit stored rule authorizes that exact transition.
```

Merely logging the discrepancy after transmission is insufficient. This check must complete before any protected content is sent.

## 14.6 IntermediateResultService

```text
create_result()
store_result_content()
link_parent_result()
list_results()
get_result()
mark_as_final()
compare_results()
export_result()
```

## 14.7 CredentialService

```text
create_reference()
resolve_reference()
test_credential()
delete_reference()
```

## 14.8 ArtifactService

```text
store_artifact()
get_artifact()
link_artifact()
verify_hash()
delete_unreferenced_artifact()
```

## 14.9 JournalService

```text
initialize_session_journal()
record_request()
record_response()
record_intermediate_result()
record_event()
record_tool_call()
record_error()
finalize_interaction()
rebuild_summary()
```

## 14.10 WorkspaceService

`WorkspaceService` is the high-level workflow orchestrator. It owns workspace policy, iteration lifecycle, journal linkage, approvals, and recovery. It delegates all low-level Git operations to `GitService`.

```text
create_workspace()
open_workspace()
prepare_ai_workspace()
start_iteration()
capture_workspace_state()
create_iteration_checkpoint()
restore_iteration()
list_iterations()
finalize_workspace_session()
```

Examples of delegated operations:

```text
prepare_ai_workspace()
    → GitService.is_repository()
    → GitService.initialize_repository(), when explicitly allowed
    → GitService.create_branch()
    → GitService.create_worktree(), when configured

create_iteration_checkpoint()
    → GitService.get_status()
    → GitService.get_diff()
    → GitService.stage_paths()
    → GitService.commit_checkpoint()
```

## 14.11 GitService

`GitService` contains only Git mechanics and has no knowledge of AI sessions, approval policy, or intermediate-result semantics.

```text
is_repository()
initialize_repository()
create_branch()
create_worktree()
remove_worktree()
get_current_commit()
get_status()
get_diff()
stage_paths()
commit_checkpoint()
create_tag()
restore_commit()
list_commits()
```

Git operations must use argument arrays, not shell-concatenated command strings.

---

## 15. File-Based Persistence

The application must not use SQL in the first version.

The core depends on storage interfaces:

```text
ConfigurationRepository
SessionRepository
ExecutionRepository
IntermediateResultRepository
ArtifactRepository
CapabilityRepository
WorkspaceRepository
```

Initial implementations:

```text
YamlConfigurationRepository
YamlSessionRepository
DirectoryExecutionRepository
DirectoryIntermediateResultRepository
ContentAddressedArtifactRepository
YamlCapabilityRepository
YamlWorkspaceRepository
```

Future SQL implementations may replace these without changing domain services.

---

## 16. Communication Journal Storage

Each normal communication session should have its own directory.

```text
sessions/
└── <session-id>/
    ├── session.yaml
    ├── conversation.md
    ├── interactions.jsonl
    ├── events.jsonl
    ├── results/
    │   ├── 0001-plan.md
    │   ├── 0002-draft.md
    │   ├── 0003-revision.md
    │   └── 0004-final.md
    ├── structured/
    │   ├── request-0001.json
    │   ├── response-0001.json
    │   └── response-0002.json
    ├── attachments.yaml
    └── artifacts/
```

### Rules

- every user interaction is appended to `interactions.jsonl`;
- every stream event may be appended to `events.jsonl`;
- every meaningful intermediate output gets its own file under `results/`;
- `conversation.md` is a generated readable journal;
- structured request and response snapshots are preserved;
- the final result is identified in `session.yaml`;
- no earlier result is overwritten.

Example result lineage:

```text
0001-plan
    └── 0002-draft
            ├── 0003-revision-a
            └── 0004-revision-b
                    └── 0005-final
```

---

## 17. Optional Git for Communication Sessions

A communication session may optionally be Git-versioned even when no project files are modified.

Use cases:

- research conversations;
- important document development;
- long iterative design discussions;
- thesis or teaching-material preparation;
- audit-sensitive communication;
- comparing how the conversation evolved.

Possible policies:

```text
disabled
manual_checkpoint
checkpoint_each_interaction
checkpoint_each_selected_result
checkpoint_session_close
```

When enabled, Git versions the session journal files:

```text
session.yaml
conversation.md
interactions.jsonl
results/
structured/
```

Secrets, browser profiles, cookies, and excluded attachments must never be committed.

---

## 18. Workspace Mode and Git

Git is mandatory whenever AI iteratively changes files.

## 18.1 Workspace structure

A workspace may use an existing repository:

```text
project/
├── .git/
├── source files
└── .ai-journal/
    └── <session-id>/
```

Alternatively, communication logs may be stored in a separate companion directory or repository to avoid polluting the project.

## 18.2 Dedicated branch or worktree

Before changes begin:

```text
main
  └── ai/<session-id>
```

Preferred for concurrent or isolated work:

```text
main repository
    +
dedicated Git worktree for AI session
```

The AI must not modify the main branch directly.

## 18.3 Iteration model

Each meaningful AI iteration is represented by one canonical schema:

```text
AIIteration
- id
- session_id
- interaction_id
- request_id
- execution_id
- sequence_number
- input_result_id
- intermediate_result_ids
- base_commit
- resulting_commit
- changed_files
- proposed_patch_reference
- final_diff_reference
- commands_log_reference
- tests_log_reference
- review_results_reference
- status
- created_at
- completed_at
- metadata
```

Field meaning:

```text
interaction_id
    The user-visible interaction that initiated the iteration.

request_id
    The normalized AI request used for the iteration.

execution_id
    The exact execution that produced the plan, patch, commands, and results.

input_result_id
    The plan, instruction, or previous result from which this iteration started.

intermediate_result_ids
    All plans, drafts, reviews, patches, and test summaries created during the iteration.

base_commit
    Git commit checked out before applying the iteration.

resulting_commit
    Git checkpoint commit created after the iteration.

proposed_patch_reference
    Initial AI-proposed patch, when available.

final_diff_reference
    Final accepted diff after corrections and tests.

commands_log_reference
    Append-only log of commands and process results.

tests_log_reference
    Test, lint, and build results.

review_results_reference
    Human or AI review findings associated with the iteration.
```

Iteration flow:

```text
1. Record user instruction.
2. Record AI plan.
3. Capture current Git base commit.
4. Apply AI file changes.
5. Record all commands and file operations.
6. Capture diff.
7. Run configured tests and checks.
8. Record AI explanation and test output.
9. Create a Git checkpoint commit.
10. Continue from that commit or restore an earlier checkpoint.
```

## 18.4 Checkpoint commits

Each meaningful iteration should produce a checkpoint commit.

Example history:

```text
a1b2c3  AI iteration 1: create adapter interface
d4e5f6  AI iteration 2: add Ollama adapter
7a8b9c  AI iteration 3: fix Windows path handling
0d1e2f  AI iteration 4: address review findings
```

Commit metadata should include the session and iteration identifiers.

Example commit message:

```text
AI iteration 3: fix Windows path handling

Session: <session-id>
Iteration: 3
AI configuration: <configuration-id>
Execution: <execution-id>
```

Checkpoint commits may later be:

- squashed;
- reordered;
- amended;
- retained as full development history;
- exported as patches.

## 18.5 Communication linkage

Every Git checkpoint must link to the exact AI communication that produced it.

The iteration metadata uses the canonical `AIIteration` schema defined above. In particular, linkage is guaranteed through:

```text
session_id
interaction_id
request_id
execution_id
intermediate_result_ids
base_commit
resulting_commit
commands_log_reference
tests_log_reference
final_diff_reference
```

The communication journal stores the resulting Git commit hash.

This creates bidirectional linkage:

```text
AI communication → Git commit
Git commit        → AI communication
```

---

## 19. Storing Intermediate File Results

A Git commit preserves the complete file state after each iteration.

Additionally, the application should store:

- the AI's plan;
- the proposed patch or diff;
- commands executed;
- stdout and stderr;
- test results;
- review feedback;
- the final diff;
- the resulting commit hash.

Suggested workspace journal:

```text
.ai-journal/
└── <session-id>/
    ├── session.yaml
    ├── conversation.md
    ├── events.jsonl
    └── iterations/
        ├── 0001/
        │   ├── instruction.md
        │   ├── plan.md
        │   ├── proposed.patch
        │   ├── commands.jsonl
        │   ├── tests.md
        │   ├── review.md
        │   ├── final.diff
        │   └── iteration.yaml
        └── 0002/
            └── ...
```

Git stores the project state.  
The journal stores the reasoning artifacts, communication, commands, tests, and linkage.

---

## 20. Artifact Storage

Attachments and generated binary files should use content-addressed storage.

```text
artifacts/
└── sha256/
    └── ab/
        └── abcdef...
```

Metadata:

```text
sha256
media_type
size
original_name
created_at
storage_path
encryption_state
```

Execution and session files refer to artifacts by hash.

---

## 21. Atomicity and Recovery

Without a database, writes must remain crash-safe.

Rules:

- write temporary files first;
- atomically rename completed files;
- use append-only JSONL for events;
- never overwrite prior intermediate results;
- use file locks where concurrent writes are possible;
- preserve incomplete executions;
- store explicit completion markers;
- make generated indexes rebuildable;
- create Git commits only after file writes and metadata are complete.

The source files are authoritative. Any indexes are disposable caches.

---

## 22. Self-Improvement Workflow

The application should be able to improve its own source code.

```text
1. Open the application's Git repository as a workspace.
2. Create an AI branch or worktree.
3. Select an AI configuration.
4. Record the requested improvement.
5. Ask the AI for a plan.
6. Store the plan as an intermediate result.
7. Apply the proposed change.
8. Store commands, patches, and tool results.
9. Run tests and static checks.
10. Create an iteration checkpoint commit.
11. Optionally ask another AI to review the diff.
12. Apply review corrections in another iteration.
13. Preserve every iteration and checkpoint.
14. Let the user approve, squash, merge, or reject the branch.
```

The application must never modify its main branch directly.

---

## 23. Security Rules

The application must:

- keep secrets out of YAML, JSON, JSONL, Markdown, and Git;
- use native OS secret stores;
- isolate browser profiles;
- prevent silent cloud fallback;
- block or explicitly confirm any declared-to-resolved location/network transition that increases exposure;
- display which files are transmitted;
- restrict CLI working directories;
- record commands and file changes;
- support read-only workspaces;
- support local-only AI configurations;
- redact secrets before writing logs;
- allow communication logging to be reduced or disabled for sensitive work;
- require explicit policy before automatic Git commits;
- prevent AI agents from rewriting Git history unless explicitly allowed.

---

## 24. Suggested Repository Layout

```text
application-data/
├── app-config.yaml
├── ai-configurations/
├── sessions/
├── executions/
├── artifacts/
├── indexes/
└── diagnostics/

application-source/
├── .git/
├── source/
├── tests/
├── docs/
└── .ai-journal/
```

For normal communication, session data lives under `application-data/sessions/`.

For file-changing work, project files live in their Git repository and the linked journal lives either:

- under `.ai-journal/`; or
- in a separate companion journal repository.

---

## 25. MVP Scope

### Include

```text
Cross-platform core
YAML AI configurations
Markdown session journal
JSON request and response snapshots
JSONL event streams
IntermediateResult model
Every meaningful intermediate result stored separately
Optional Git versioning for communication sessions
Mandatory Git workflow for file-changing sessions
Dedicated AI branch or worktree
Git checkpoint per meaningful file iteration
Bidirectional communication-to-commit linkage
OpenAI-compatible adapter
One cloud API adapter
One browser adapter
Generic CLI adapter
Basic session and execution UI
Workspace diff and history view
```

### Exclude initially

```text
SQL database
ORM
Automatic model routing
Automatic cloud fallback
Comparison mode and comparison service
Distributed scheduling
Multi-user permissions
Autonomous uncontrolled agents
Automatic merge to main
Automatic history rewriting
Universal CLI attachment handling
```

---

## 26. Primary Communication Flow

```text
1. User opens or creates a communication session.
2. User selects an AI configuration.
3. User sends input.
4. Request snapshot is stored.
5. The adapter resolves the actual endpoint, location, and network path.
6. ExposureTransitionPolicy is evaluated before protected content is sent.
7. Execution starts only if the transition is allowed or explicitly confirmed.
8. Stream events are appended.
9. Meaningful intermediate results are assembled and stored separately.
10. User may ask for revision, branch from a result, or switch AI.
11. Every new result is linked to its parent.
12. User selects the preferred final result.
13. The session journal is rebuilt.
14. The session may optionally receive a Git checkpoint.
```

---

## 27. Primary Workspace Flow

```text
1. User opens a Git workspace.
2. Application creates or selects a dedicated AI branch/worktree.
3. User selects an AI configuration.
4. Instruction and source context are stored locally.
5. The adapter resolves the actual endpoint, location, and network path.
6. ExposureTransitionPolicy is evaluated before source context is transmitted.
7. AI produces a plan only after the transition is allowed or explicitly confirmed.
8. Plan is stored as an intermediate result.
9. AI changes files.
10. Commands, patches, and file operations are recorded.
11. Tests and checks run.
12. Diff and review output are stored.
13. A Git checkpoint commit is created.
14. The next AI iteration starts from that commit.
15. User can restore, compare, squash, merge, or reject iterations.
```

---

## 28. Post-MVP Comparison Design

Comparison is deliberately excluded from the MVP.

A later implementation should use:

```text
ComparisonGroup
- id
- session_id
- source_interaction_id
- configuration_ids
- execution_ids
- created_at
- status
```

The same logical input is copied into several sibling `Interaction` objects. Each sibling interaction has exactly one `configuration_id` and one independent `Execution`.

```text
AISession
    └── ComparisonGroup
            ├── Interaction using configuration A
            ├── Interaction using configuration B
            └── Interaction using configuration C
```

A future `ComparisonService` will coordinate these executions but will delegate every individual run to `ExecutionManager`.

---

## 29. Later SQL Migration

The application core should depend on repository interfaces, not file paths directly.

Possible future implementations:

```text
SqlSessionRepository
SqlExecutionRepository
SqlIntermediateResultRepository
SqlWorkspaceRepository
```

SQL is justified later if there are:

- very large histories;
- complex cross-session queries;
- several concurrent processes;
- remote multi-user deployment;
- transactional multi-record requirements.

The file and Git history can remain as exports and reproducibility artifacts.

---

## 30. Success Criteria

The project is successful when:

- it runs on macOS, Linux, and Windows;
- arbitrary AI configurations can coexist;
- each execution records where the AI ran and how its endpoint was reached;
- exposure-increasing connectivity mismatches are blocked or explicitly approved before transmission;
- normal communication preserves every meaningful intermediate result;
- no AI result is silently overwritten;
- revisions form an inspectable history or tree;
- communication sessions can optionally be Git-versioned;
- all AI-driven file changes occur in Git repositories;
- every meaningful file iteration has a checkpoint commit;
- each commit links to the exact AI communication that produced it;
- every AI-assisted change can be inspected, tested, restored, or rejected;
- secrets never enter ordinary logs or repositories;
- the application can safely use AI to improve itself;
- SQL can be added later without redesigning the domain.

---

## 31. Final Design Principle

There are two forms of history:

```text
Communication history
    Every prompt, response, revision, tool result, and intermediate answer.

Workspace history
    Every file state, patch, test result, review, and Git checkpoint.
```

Both histories must be linked.

> Normal AI work preserves every meaningful result. File-changing AI work additionally preserves every iteration as Git history.
