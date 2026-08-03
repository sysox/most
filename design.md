# Multi-Provider AI Access Application

**Specification version:** 12 — Final MVP Design

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

This version is the final architectural specification for the MVP. Implementation details may refine types and signatures, but must preserve the stated safety and history guarantees.

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

- a small implementation surface;
- minimal dependencies;
- readable files;
- Git-friendly history;
- easy manual inspection;
- easy AI-assisted improvement;
- replaceable persistence interfaces;
- no SQL database;
- no ORM;
- no database migrations;
- safe failure instead of silent degradation.

The MVP is divided into two layers:

```text
MVP Safety Kernel
    Required before protected data can be transmitted or workspace files can
    be changed.

Progressive Detection Enhancements
    Improve automation and confidence but may initially return DECLARED or
    UNKNOWN instead of making unreliable guesses.
```

The safety kernel includes explicit policy resolution, deterministic context assembly, single-writer persistence, complete process-tree cancellation, recoverable leases, isolated Git workspaces, and browser-profile path isolation.

Advanced route inspection, language-specific symbol extraction, provider-specific tokenization, and browser selector diagnosis may be implemented progressively. Missing automation must result in an explicit conservative state that fails, pauses, or requires confirmation.

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
├── NetworkInspector
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

Required platform-level operations include:

```text
ProcessService
- create_process_isolation()
- terminate_process_tree()
- release_process_isolation()

BrowserProfileService
- validate_isolated_profile_path()

NetworkInspector
- inspect_endpoint_path()
- return confidence and evidence
```

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
- exposure_transition_policy_reference
- context_overflow_policy
- workspace_context_strategy
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

Policy and strategy resolution use these precedence rules:

```text
ExposureTransitionPolicy
1. per-execution override, only when explicitly permitted by the configuration;
2. AIConfiguration.exposure_transition_policy_reference;
3. application default exposure policy;
4. built-in default: FAIL.

Context overflow policy
1. per-request override;
2. AIConfiguration.context_overflow_policy;
3. application default context-overflow policy;
4. built-in default: FAIL.

Workspace context strategy
1. per-interaction override;
2. AIConfiguration.workspace_context_strategy;
3. workspace default;
4. built-in default: EXPLICIT_SELECTION.
```

A less restrictive exposure override requires explicit user confirmation. Every resolved policy and strategy is copied into the request, context, or execution snapshot so historical behavior remains reproducible.

## 7.4 WorkspaceContextStrategy

Controls how source files are selected and injected into an AI request in Workspace Mode.

```text
WorkspaceContextStrategy
- mode
- include_patterns
- exclude_patterns
- max_files
- max_bytes
- max_tokens
- symbol_depth
- snippet_radius
- include_git_diff
- include_untracked_files
- require_confirmation
```

Supported modes:

```text
EXPLICIT_SELECTION
    Include only files or symbols explicitly selected by the user.

GIT_DIFF_ONLY
    Include the current base-to-worktree diff and directly referenced files.

CHANGED_FILES
    Include files changed in selected current or prior iterations.

SYMBOL_SUMMARY
    Include repository structure and symbol summaries, with full text only for
    selected symbols or files.

SNIPPET_WINDOWS
    Include bounded line ranges around search hits, diagnostics, or symbols.

REPOSITORY_MAP
    Include a compact tree and file summaries, then retrieve details on demand.

ADAPTER_NATIVE
    Allow an approved coding agent to discover context within its explicit
    workspace permissions.

HYBRID
    Combine a repository map, Git diff, selected files, and bounded snippets.
```

Rules:

- full-repository injection is never the default;
- ignored, secret, generated, and out-of-workspace paths are excluded;
- every included file, symbol, snippet, diff, and summary is recorded;
- source content shares the same token budget as conversation history and tools;
- source files are never silently truncated;
- generated source summaries are stored as `IntermediateResult` objects;
- `ADAPTER_NATIVE` requires explicit workspace capabilities and approved filesystem scope.

## 7.5 AccessMethod

```text
AccessMethod
- id
- type
- adapter_type
- display_name
- configuration_schema
- supported_features
```

## 7.6 CredentialReference

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

## 7.7 ExposureTransitionPolicy

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

## 7.8 LoggingPolicy

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

## 7.9 Common Type and Reference Conventions

All persistent records use explicit, portable types.

```text
ID
    UUIDv7 or ULID encoded as a lowercase string.

Timestamp
    UTC RFC 3339 with millisecond precision.

PathReference
    A platform-neutral logical reference plus an optional resolved local path.

ArtifactReference
    Content hash plus artifact metadata reference.

SecretReference
    Opaque identifier resolved only through CredentialService.

Money
    Decimal amount plus ISO currency code; never binary floating point.

TokenCount
    Non-negative integer plus estimator name and estimator version.

Metadata
    JSON-compatible object with namespaced extension keys.
```

### Versioned persisted-record header

Every top-level record persisted as YAML, JSON, or one line of JSONL includes the following flattened header:

```text
PersistedRecordHeader
- schema_version
- record_type
- record_id
- written_at
- writer_application_version
```

Field rules:

```text
schema_version
    Positive integer identifying the schema of that record type.

record_type
    Stable namespaced type identifier, for example:
    AI_CONFIGURATION, EXECUTION, STREAM_EVENT, AI_ITERATION.

record_id
    Stable ID of the serialized record.

written_at
    Timestamp at which this serialized representation was written.

writer_application_version
    Application version that produced the record.
```

The header is flattened into the top-level object rather than nested under another key.

The domain schemas below list their domain-specific fields and may omit these inherited serialization fields for readability. They do not omit them from the persisted representation.

For a domain object that already has `id`, `record_id` must equal `id`. For singleton records such as `ApplicationSettings`, `record_id` is the stable `application_instance_id`.

Each JSONL line is independently versioned because lines must remain parseable and recoverable without relying on a file-level header.

Readers and writers follow these rules:

- writers emit exactly one currently supported schema version for each record type;
- readers dispatch by `(record_type, schema_version)`;
- readers may migrate older supported versions in memory;
- unsupported newer versions are preserved or rejected explicitly, never partially reinterpreted;
- unknown fields are retained when records are read and rewritten where practical;
- migrations must not overwrite the original record silently;
- schema-version changes require fixtures and compatibility tests.

General rules:

- IDs are immutable and globally unique within an application-data root;
- timestamps ending in `_at` are UTC;
- references ending in `_id` refer to persistent records;
- references ending in `_reference` refer to files, artifacts, secrets, or external provider objects;
- lists are empty rather than `null` unless absence has distinct meaning;
- optional scalar fields are explicitly nullable;
- enums use uppercase values in persisted YAML/JSON;
- internal Python or application names may use lowercase, but serialization is canonical;
- unknown enum values must be preserved when reading newer records, not silently discarded.

## 7.10 ApplicationSettings

Application-wide defaults and service configuration are owned by one explicit record.

```text
ApplicationSettings
- application_instance_id
- default_exposure_transition_policy_reference
- default_context_overflow_policy
- default_workspace_context_strategy
- application_data_root
- browser_profile_root
- temporary_workspace_root
- artifact_root
- default_logging_policy
- lease_timeout_seconds
- process_cancel_grace_seconds
- event_flush_interval_ms
- created_at
- updated_at
```

`ApplicationSettings` is stored in `app-config.yaml` and inherits `PersistedRecordHeader`. Its `record_id` equals `application_instance_id`. Per-configuration and per-request values override these defaults only according to the precedence rules in §7.3.

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
- active_result_id
- origin_session_id
- origin_result_id
- status
- metadata
```

Possible MVP modes:

```text
COMMUNICATION
WORKSPACE
```

`COMPARISON` is intentionally excluded from the MVP domain model. A later comparison feature may model one comparison session as several sibling interactions, each using a different `AIConfiguration`, linked by a `comparison_group_id`.

The session mode is immutable after creation. A session does not change in place from `COMMUNICATION` to `WORKSPACE`.

When a user decides to apply a communication result to files, the application creates a new `WORKSPACE` session linked through:

```text
origin_session_id
origin_result_id
```

The original communication session remains unchanged and auditable. The UI may present the new workspace session as a continuation, but persistence treats it as a separate session with separate rules.

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

## 9.5 ContextAssemblyRecord

Before a provider request is created, the application must record exactly how the stored session tree was converted into the linear context sent to the selected AI.

```text
ContextAssemblyRecord
- id
- session_id
- interaction_id
- active_result_id
- lineage_result_ids
- included_message_ids
- included_attachment_ids
- excluded_result_ids
- excluded_message_ids
- transformations
- workspace_context_strategy
- included_workspace_files
- included_workspace_symbols
- included_workspace_snippets
- included_git_diffs
- excluded_workspace_paths
- token_estimate
- token_limit
- overflow_policy
- created_at
- metadata
```

### Branch-to-context rule

For a request branching from an intermediate result:

1. Start at `active_result_id`.
2. Follow `parent_result_id` links to the root.
3. Reverse that path to obtain root-to-leaf order.
4. Include only interactions, messages, tool results, and attachments referenced by that active lineage.
5. Exclude sibling branches unless the user explicitly imports them.
6. Convert the selected lineage into provider-compatible linear messages.
7. Persist the exact selection and transformations in `ContextAssemblyRecord`.

This makes the context deterministic and reproducible.

### Context overflow policy

Context must be estimated before transmission using a provider-specific token estimator when available and a conservative fallback otherwise.

Supported policies:

```text
FAIL
    Reject the request and show the estimated overflow.

TRIM_OLDEST
    Remove the oldest eligible context items while preserving system rules,
    the active user request, and explicitly pinned results.

SUMMARIZE_WITH_CONFIRMATION
    Create a stored summary of older context, show what will be replaced,
    and require approval before using the summary.

SELECT_MANUALLY
    Ask the user to select messages, results, or files to include.
```

The default policy is `FAIL`. Trimming or summarization must never occur silently.

A generated summary is itself an `IntermediateResult` and must record:

```text
source_result_ids
source_message_ids
source_file_references
summary_configuration_id
summary_execution_id
```

### Workspace context assembly

In Workspace Mode, `ContextAssemblyService` resolves both the active conversation lineage and source context selected by the resolved `WorkspaceContextStrategy`.

The exact repository map, files, symbols, snippets, Git diffs, summaries, and exclusions used for the request are stored in `ContextAssemblyRecord`.

The shared context budget includes:

```text
system and developer instructions
+ active conversation lineage
+ tool results
+ repository maps or summaries
+ source files and snippets
+ Git diffs
+ current user request
+ reserved output budget
```

The current request, mandatory system rules, and explicitly pinned source items are protected from automatic removal. Source files must not be silently truncated. Any summarization follows the configured overflow policy and creates a traceable `IntermediateResult`.

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
- observability_level
- state
- waiting_reason
- platform
- host_identifier
- resolved_endpoint
- resolved_location
- resolved_network
- network_resolution_confidence
- network_resolution_evidence_reference
- created_at
- updated_at
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

`WORKSPACE_DIVERGED` is not a top-level execution state. It is represented as:

```text
state: waiting_for_user
waiting_reason: WORKSPACE_DIVERGED
```

Other standardized waiting reasons include:

```text
AUTHENTICATION_REQUIRED
CAPTCHA_REQUIRED
EXPOSURE_CONFIRMATION_REQUIRED
CONTEXT_SELECTION_REQUIRED
COMMAND_APPROVAL_REQUIRED
STALE_LEASE_TAKEOVER_REQUIRED
```

This keeps lifecycle state separate from the reason user action is required.

### Execution lifecycle transitions

Only the following state transitions are valid:

```text
created → validating
validating → ready | waiting_for_user | failed | cancelled
ready → starting | cancelled
starting → running | waiting_for_user | failed | cancelled
running → streaming | waiting_for_user | completed | failed | cancelled
streaming → waiting_for_user | completed | failed | cancelled
waiting_for_user → ready | running | streaming | failed | cancelled
```

`completed`, `failed`, and `cancelled` are terminal states. No transition out of a terminal state is valid.

A retry or recreated request creates a new `Execution`; terminal records are immutable except for append-only audit annotations.

Every transition is persisted as a `StatusEvent` before the derived execution snapshot is updated.

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
- observation_source
- observation_confidence
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
external_agent_run
workspace_divergence
```

An `ExecutionStep` must only claim detail that the adapter actually observed. It must not fabricate tool calls or internal reasoning for an opaque CLI or browser execution.

Possible `observation_source` values:

```text
PROVIDER_EVENT
STRUCTURED_CLI_OUTPUT
TEXT_STREAM
FILESYSTEM_DIFF
PROCESS_METADATA
BROWSER_DOM
INFERRED
```

Inferred steps must be marked explicitly and carry lower confidence.

## 10.2 StreamEvent

Every stream event shares a common envelope:

```text
StreamEvent
- event_id
- execution_id
- sequence_number
- event_type
- created_at
- observation_source
- payload
- previous_event_hash
- event_hash
```

Supported event types include:

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

`sequence_number` is strictly increasing within one execution. Event hashes are optional for ordinary sessions and required when tamper-evident audit logging is enabled.

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
validate_configuration(configuration) -> ValidationReport
test_connection(configuration, credential_handle?) -> ConnectionReport
get_capabilities(configuration, credential_handle?) -> CapabilityReport
get_observability_profile(configuration) -> AdapterObservabilityProfile
resolve_connectivity(configuration) -> ConnectivityResolution
list_models(configuration, credential_handle?) -> list[ModelDescriptor]
execute(context) -> AIResponse
stream(context) -> AsyncIterator[StreamEvent]
cancel(cancellation_handle) -> CancellationReport
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

## 12.1 AdapterExecutionContext

Adapters receive one fully resolved execution context rather than independently loading configuration or secrets.

```text
AdapterExecutionContext
- execution_id
- request_snapshot
- configuration_snapshot
- effective_capabilities
- context_assembly_record
- resolved_connectivity
- credential_handle
- workspace_scope
- cancellation_handle
- event_sink
- platform_services
```

Rules:

- `credential_handle` is opaque and short-lived;
- adapters must not read configuration repositories directly;
- adapters emit events only through `event_sink`;
- adapters write no journal files directly;
- workspace access is limited to `workspace_scope`;
- `cancel(cancellation_handle)` receives the same opaque handle stored in `AdapterExecutionContext.cancellation_handle`;
- the handle may represent a provider request, POSIX process group, Windows Job Object, browser task, or adapter-specific cancellation primitive;
- the context snapshot is immutable for the duration of an execution.

## 12.2 Adapter Observability

Adapters do not all expose the same internal detail. Each adapter must declare an `AdapterObservabilityProfile`.

```text
GRANULAR
    Structured provider events expose model generations, tools, and results.

STRUCTURED_STREAM
    Structured stream events are available, but internal provider loops may
    remain partly opaque.

TEXT_STREAM
    Only text or process output can be streamed reliably.

BLOCK
    The application can observe only start, completion, status, files, and
    final output.

OPAQUE
    Only invocation and coarse completion/failure are observable.
```

`ExecutionManager` and the UI must respect this profile. Fine-grained `ExecutionStep` records are optional and must never be invented to satisfy a uniform schema.

For `BLOCK` or `OPAQUE` executions, one coarse `external_agent_run` step is valid, supplemented by independently observable process metadata, filesystem diffs, generated files, and test results.

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

## 13.1 CLI Adapter Rules

A CLI adapter must assume that an external AI agent may control its own hidden loop.

The generic CLI adapter is required to capture only what is externally observable:

```text
redacted executable and argument list
working directory
allowed environment-variable names
start and finish time
stdout and stderr
exit status
cancellation result
files changed before and after execution
Git diff
generated files
tests run by the application
```

If the CLI offers a documented structured event format, a specialized adapter may emit granular steps. Otherwise, the execution is modeled as one `external_agent_run` block. The application must not claim to know the CLI's internal tool calls.

### Process-tree isolation and cancellation

Every CLI execution must run inside an operating-system process container that permits full descendant-tree termination.

```text
macOS/Linux
    Start the CLI in a new process group or session.
    Graceful cancellation sends SIGTERM to the process group.
    Forced cancellation sends SIGKILL to the process group after timeout.

Windows
    Assign the process to a Windows Job Object.
    Configure JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
    Closing or terminating the Job Object stops the full descendant tree.
```

Cancellation sequence:

```text
1. mark cancellation_requested;
2. stop accepting new approvals;
3. terminate the complete process tree gracefully;
4. wait for the configured grace period;
5. force termination of remaining descendants;
6. verify that no tracked descendant remains;
7. rescan workspace status and file hashes;
8. record incomplete or out-of-band changes.
```

Killing only the parent process is not a valid implementation of `cancel()`. Process isolation does not imply visibility into the external agent's internal loop.

## 13.2 Browser Adapter Recovery

Browser adapters are expected to be fragile and must use versioned provider-specific selector packs.

A browser adapter should:

- prefer semantic roles, labels, and stable attributes over positional selectors;
- record the selector-pack and adapter version;
- capture a screenshot and sanitized DOM snapshot on failure;
- allow a bounded retry, reload, or new-page attempt;
- pause in `waiting_for_user` for login, 2FA, CAPTCHA, consent dialogs, or ambiguous UI;
- detect rate-limit and provider-error pages;
- abort rather than click an unrecognized control;
- never silently fall back to an API, CLI, or different provider.

A provider UI change that invalidates selectors creates a failed or paused execution. Recovery requires a selector-pack update or explicit user intervention.

### Browser profile path isolation

Browser profiles must live only under the platform-managed directory controlled by `BrowserProfileService`.

They must never reside:

- inside a communication session directory;
- inside `.ai-journal/`;
- inside a source workspace;
- inside a Git worktree or repository;
- inside an export directory.

`BrowserProfileService` resolves canonical paths and rejects any overlap with journals, workspaces, exports, or repositories. Generated `.gitignore` rules are only defense in depth and are not a sufficient primary control.

Cookies, OAuth data, local storage, caches, and browser databases must never be copied into session journals or Git exports.

## 13.3 Connectivity Resolution and Uncertainty

Network-path discovery is inherently imperfect.

`resolve_connectivity()` returns:

```text
ConnectivityResolution
- endpoint
- location
- network
- confidence
- evidence
```

Confidence values:

```text
VERIFIED
    Supported by strong platform evidence.

INFERRED
    Derived from DNS, address ranges, interfaces, routes, proxies, or VPN state.

DECLARED
    Taken from explicit trusted configuration because automatic resolution
    was unavailable.

UNKNOWN
    The adapter and platform services could not classify the path safely.
```

`NetworkInspector` may inspect:

- URL scheme and final host;
- DNS resolution;
- loopback, private, public, and overlay IP ranges;
- active interfaces;
- routing table;
- proxy settings;
- known VPN or Tailscale interfaces;
- redirects before protected request bodies are transmitted.

The application must not treat `UNKNOWN` as private or safe. The default exposure policy for `UNKNOWN` is `FAIL` or `REQUIRE_CONFIRMATION`.

Explicit endpoint tagging is permitted, but the record must state that confidence is `DECLARED`, not `VERIFIED`. Exposure-changing redirects must not be followed automatically with protected content.

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
create_workspace_from_result()
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
recover_stale_workspace_lease()
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
inspect_submodules()
inspect_lfs()
check_path_length_support()
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

## 14.12 ContextAssemblyService

```text
resolve_active_lineage()
resolve_workspace_context()
build_repository_map()
select_file_snippets()
assemble_messages()
estimate_tokens()
apply_overflow_policy()
create_context_record()
```

It is the only service responsible for converting a result tree into the linear payload passed to an adapter.

## 14.13 ConnectivityService

```text
resolve_connectivity()
collect_network_evidence()
compare_declared_and_resolved()
evaluate_exposure_transition()
```

It coordinates adapter observations with `NetworkInspector` and returns uncertainty explicitly.

## 14.14 PersistenceCoordinator

All runtime file mutations must pass through a single-writer persistence coordinator.

```text
enqueue_write()
append_event_batch()
write_atomic_snapshot()
flush_execution()
rebuild_derived_document()
acquire_data_root_lease()
recover_stale_data_root_lease()
release_data_root_lease()
```

Adapters and UI components publish events; they do not write journal files directly.

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

### Authoritative file locations

```text
app-config.yaml
    ApplicationSettings and schema version.

ai-configurations/<configuration-id>.yaml
    Current AIConfiguration records.

capabilities/<configuration-id>.yaml
    Discovered capability snapshots.

sessions/<session-id>/session.yaml
    AISession source of truth.

sessions/<session-id>/interactions.jsonl
    Ordered Interaction records.

sessions/<session-id>/results/<result-id>.md
    Human-readable IntermediateResult content.

sessions/<session-id>/structured/<record-id>.json
    Requests, responses, context records, and structured results.

executions/<yyyy>/<mm>/<execution-id>/metadata.yaml
    Execution source of truth.

executions/<yyyy>/<mm>/<execution-id>/events.jsonl
    Ordered StreamEvent journal.

workspaces/<workspace-id>.yaml
    Workspace configuration and journal linkage.

artifacts/sha256/<prefix>/<hash>
    Content-addressed artifact bytes.

indexes/
    Rebuildable caches only; never authoritative.
```

Session records reference execution IDs; execution records reference session, interaction, request, and configuration snapshot IDs. Workspace journals may live with a project, but the application-data record remains the authoritative pointer to their canonical location.

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

## 18.6 Dirty Working Tree Policy

Workspace preparation must inspect tracked, untracked, staged, and ignored state before an AI iteration begins.

Supported policies:

```text
REQUIRE_CLEAN
    Refuse to start until the user resolves local changes.

ISOLATE_FROM_HEAD
    Create a dedicated worktree from the current committed HEAD. Existing
    uncommitted edits remain untouched and are not included.

IMPORT_USER_SNAPSHOT
    With explicit approval, capture selected user changes into a patch,
    apply them to the AI worktree, and create a clearly marked user-baseline
    checkpoint before any AI commit.

STASH_WITH_CONFIRMATION
    Stash selected changes only after explicit confirmation and record the
    stash reference for recovery.
```

The default is `ISOLATE_FROM_HEAD` when a worktree can be created; otherwise `REQUIRE_CLEAN`.

Unrelated user edits must never be silently included in an AI checkpoint.

## 18.7 Worktree Compatibility and Fallback

Before creating an AI worktree, `GitService` inspects:

- repository dirty state;
- registered worktrees;
- submodule state;
- Git LFS usage and object availability;
- filesystem permissions;
- destination path length;
- Windows long-path support.

Fallback order:

```text
DEDICATED_WORKTREE
        ↓ unavailable or unsafe
ISOLATED_TEMPORARY_CLONE_OR_CHECKOUT
        ↓ unavailable
REQUIRE_CLEAN_WORKING_TREE
        ↓ not satisfied
REFUSE_WORKSPACE_SESSION
```

An isolated temporary clone or checkout must use a separate path and must never apply AI changes directly inside a dirty user working tree.

### Submodules

- record required submodule commit hashes;
- initialize submodules explicitly according to policy;
- do not share mutable submodule worktrees across AI sessions;
- pause when a required submodule cannot be materialized.

### Git LFS

- detect LFS pointer files;
- verify required objects before presenting content to the AI;
- do not silently substitute pointer text for expected content;
- permit metadata-only handling only when explicitly configured.

### Windows paths

- use a short platform-managed checkout root;
- use compact session identifiers;
- detect long-path support before checkout;
- select a shorter isolated path or fail before editing begins.

The selected isolation tier and every fallback decision are stored in workspace metadata.

## 18.8 Concurrent Modification and Workspace Leases

Each AI worktree has at most one active writer.

`WorkspaceService` must acquire a workspace lease containing:

```text
lease_id
session_id
process_id
host_identifier
started_at
heartbeat_at
lease_timeout_seconds
```

Git operations are serialized per repository through `GitService`.

Before applying a patch and before committing, the application compares file hashes and Git status with the expected workspace state. Unexpected changes produce:

```text
WORKSPACE_DIVERGED
```

The iteration pauses and requires the user to:

```text
accept_external_changes
discard_external_changes
restart_from_checkpoint
create_new_iteration
```

The application must not guess whether simultaneous editor changes belong to the user or the AI.

### Stale workspace lease recovery

1. Read the lease atomically.
2. If `host_identifier` matches the local host, check whether `process_id` exists.
3. A live process with a fresh heartbeat keeps the lease active.
4. A missing process marks the lease stale.
5. An expired heartbeat marks it suspect because PID reuse is possible.
6. Inspect Git locks, child processes, and workspace state.
7. Automatically recover only a verified dead local process when policy permits.
8. Otherwise require explicit takeover confirmation.
9. Replace the lease atomically and record `stale_lease_recovered`.
10. Never automatically break a lease owned by another host.

## 18.9 Checkpoint and History Compaction Policy

A meaningful iteration is a user-visible plan/edit/test/review cycle, not every individual file write or failed internal attempt.

Supported checkpoint policies:

```text
PER_SUCCESSFUL_ITERATION
PER_APPROVED_ITERATION
MANUAL
DEBUG_ALL
```

Failed attempts and tiny corrections remain in the journal even when they do not create commits.

At workspace-session finalization, the user chooses:

```text
KEEP_DETAILED_HISTORY
SQUASH_TO_ONE_COMMIT
SQUASH_BY_APPROVED_ITERATION
EXPORT_PATCH_SERIES
DISCARD_BRANCH
```

History rewriting or squashing requires explicit confirmation. Journal records are never squashed and continue to preserve the complete AI process.

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

## 21.1 Single-Writer Persistence and Windows Compatibility

The MVP uses one `PersistenceCoordinator` as the sole writer for one application-data root.

Rules:

- adapters, workers, and UI components enqueue persistence operations;
- JSONL events are appended in small batches and the file handle is closed after each flush;
- `conversation.md` and other derived documents are rebuilt through temporary-file plus atomic-replace, not continuously appended by several components;
- the UI receives live events through an in-memory event bus and reads disk snapshots only after the writer publishes completion;
- a data-root lease prevents a second application process from writing to the same journal concurrently;
- readers must tolerate a final partial JSONL line after a crash and ignore it during recovery;
- Windows-specific open/share behavior is implemented inside the storage backend;
- `EBUSY`, `EACCES`, and transient antivirus/indexer locks use bounded retry with backoff;
- no component holds long-lived read handles on files that the writer must replace.

Multi-process concurrent writers are excluded from the MVP.

### Stale data-root lease recovery

The data-root lease stores:

```text
lease_id
process_id
host_identifier
started_at
heartbeat_at
lease_timeout_seconds
```

On startup, a matching local host permits an OS process-existence check. A missing process marks the lease stale; an expired heartbeat marks it suspect. Before takeover, the application inspects temporary files and JSONL tails.

Automatic recovery is allowed only for a verified dead local process when policy permits; otherwise explicit confirmation is required. A takeover is written atomically and records `stale_lease_recovered`. A lease owned by another host is never broken automatically.

After a crash, recovery may ignore one incomplete final JSONL line and repair unfinished temporary-file writes.

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
- prevent AI agents from rewriting Git history unless explicitly allowed;
- treat unknown network resolution as unsafe by default;
- never fabricate granular activity for opaque CLI or browser adapters;
- pause on workspace divergence instead of combining concurrent edits;
- terminate the complete CLI process tree on cancellation;
- keep browser profiles outside journals, workspaces, exports, and Git repositories;
- recover stale leases only through verified or explicitly approved takeover;
- refuse workspace execution when no safe Git isolation tier is available.

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

The MVP is implementation-ready when the Safety Kernel is present. The following components may initially use conservative fallbacks:

```text
NetworkInspector
    May return DECLARED or UNKNOWN when route inspection is unavailable.

Workspace symbol extraction
    May begin with file maps, Git diffs, explicit selection, and text snippets.

Token estimation
    May use conservative estimators until provider-specific tokenizers exist.

Browser diagnostics
    May require manual selector-pack updates.
```

Uncertain states must fail, pause, or require explicit confirmation.

### Include

```text
Cross-platform core
YAML AI configurations
Markdown session journal
JSON request and response snapshots
JSONL event streams
IntermediateResult model
Every meaningful intermediate result stored separately
Deterministic branch-to-context assembly
WorkspaceContextStrategy for repository maps, diffs, symbols, snippets, and explicit file selection
Explicit context-overflow policies
Adapter observability profiles
Connectivity resolution with confidence and evidence
Single-writer persistence coordinator
Windows-safe event and snapshot writing
Stale lease recovery for data roots and workspaces
Cross-platform process-tree isolation and full subtree termination
Git worktree compatibility inspection and fallback tiers
Strict browser-profile path isolation
Immutable session modes with communication-to-workspace forking
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
Deep introspection of opaque external CLI agent loops
Automatic browser-selector self-repair
Perfect automatic VPN/Tailscale route classification on every platform
Language-specific AST indexing for every programming language
Multi-process writers for one application-data root
Universal CLI attachment handling
```

---

## 26. Primary Communication Flow

```text
1. User opens or creates a communication session.
2. User selects an AI configuration.
3. User chooses the active result or branch and sends input.
4. ContextAssemblyService resolves the root-to-active-result lineage.
5. In Workspace Mode, it also applies the resolved WorkspaceContextStrategy.
6. Token budget is estimated across messages, source context, diffs, tools, and reserved output.
7. The configured overflow policy is applied without silent truncation.
8. ContextAssemblyRecord and request snapshot are stored.
9. The adapter and NetworkInspector resolve endpoint, location, network, confidence, and evidence.
10. ExposureTransitionPolicy is evaluated before protected content is sent.
11. Execution starts only if the transition is allowed or explicitly confirmed.
12. Observable stream events are published to the in-memory event bus.
13. PersistenceCoordinator appends events and stores meaningful intermediate results.
14. User may ask for revision, branch from a result, or switch AI.
15. Every new result is linked to its parent.
16. User selects the preferred final result.
17. The session journal is rebuilt atomically.
18. The session may optionally receive a Git checkpoint.
```

---

## 27. Primary Workspace Flow

```text
1. User opens a Git workspace.
2. WorkspaceService inspects dirty state, submodules, LFS, path support, and available isolation tiers.
3. Application creates the safest available isolated checkout and acquires a recoverable workspace lease.
4. User selects an AI configuration.
5. ContextAssemblyService applies the resolved WorkspaceContextStrategy to select repository maps, diffs, files, symbols, snippets, and prior results within the token budget.
6. Instruction, context manifest, and hashes are stored locally.
7. Connectivity is resolved with confidence and ExposureTransitionPolicy is evaluated.
8. AI produces a plan only after the transition is allowed or explicitly confirmed.
9. Plan is stored as an intermediate result.
10. AI or the external CLI agent changes files according to its observability profile.
11. CLI agents run inside a POSIX process group/session or Windows Job Object.
12. Commands, process output, patches, and independently observed file changes are recorded.
13. Workspace hashes and Git state are checked for unexpected concurrent edits.
14. Tests and checks run.
15. Diff and review output are stored.
16. A checkpoint is created according to checkpoint policy.
17. The next AI iteration starts from that checkpoint.
18. User can restore, compare, compact, merge, export, or reject iterations.
19. Workspace lease is released when the session pauses or completes.
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

## 30. Pre-Build Implementation Checklist

The MVP implementation may begin when each item has an explicit decision, test, or stub with conservative behavior.

### Domain and serialization

- [ ] Define canonical enums and nullable fields.
- [ ] Implement `PersistedRecordHeader` on every YAML, JSON, and JSONL record.
- [ ] Implement tolerant readers and strict writers.
- [ ] Validate all cross-record references.
- [ ] Use UTC timestamps and stable IDs consistently.

### Adapter boundary

- [ ] Implement `AdapterExecutionContext`.
- [ ] Confirm each adapter's observability profile.
- [ ] Ensure adapters cannot write journals or resolve secrets independently.
- [ ] Implement connectivity resolution with explicit confidence.
- [ ] Implement cancellation reports and complete subprocess-tree termination.

### Context and privacy

- [ ] Record every context-assembly decision.
- [ ] Enforce shared token budgets.
- [ ] Default workspace context to explicit selection.
- [ ] Resolve exposure and overflow policies using documented precedence.
- [ ] Block transmission until exposure checks complete.

### Persistence and recovery

- [ ] Implement one `PersistenceCoordinator` writer.
- [ ] Use atomic replacement for snapshots and append-only JSONL for events.
- [ ] Implement stale data-root and workspace lease recovery.
- [ ] Verify Windows sharing, retry, and antivirus-lock behavior.
- [ ] Rebuild indexes entirely from authoritative files.

### Workspace and Git

- [ ] Detect dirty state, submodules, LFS, and path constraints.
- [ ] Implement the isolation fallback chain.
- [ ] Acquire one active-writer workspace lease.
- [ ] Detect divergence before patching and committing.
- [ ] Link each checkpoint bidirectionally with its AI execution.
- [ ] Require confirmation for merge, squash, history rewrite, or destructive recovery.

### Security

- [ ] Store credentials only through native or encrypted secret stores.
- [ ] Reject browser-profile paths overlapping repositories or journals.
- [ ] Redact secrets before persistence and export.
- [ ] Treat unknown connectivity as unsafe.
- [ ] Verify that sensitive logging can be disabled without breaking execution.

---

## 31. Success Criteria

The project is successful when:

- it runs on macOS, Linux, and Windows;
- arbitrary AI configurations can coexist;
- each execution records where the AI ran and how its endpoint was reached;
- exposure-increasing connectivity mismatches are blocked or explicitly approved before transmission;
- uncertain connectivity is represented explicitly and never silently treated as private;
- normal communication preserves every meaningful intermediate result;
- branched result trees are converted into deterministic, recorded provider context;
- workspace source context is selected through an explicit, recorded strategy;
- context overflow never causes silent trimming, source truncation, or summarization;
- no AI result is silently overwritten;
- revisions form an inspectable history or tree;
- communication sessions can optionally be Git-versioned;
- all AI-driven file changes occur in Git repositories;
- every meaningful file iteration has a checkpoint commit;
- each commit links to the exact AI communication that produced it;
- dirty user work is isolated from AI checkpoint commits;
- concurrent workspace edits are detected and paused rather than merged implicitly;
- opaque adapters record only observable facts;
- CLI cancellation terminates the complete descendant process tree;
- stale data-root and workspace leases can be recovered safely after crashes;
- worktree failures caused by submodules, LFS, or path constraints follow explicit isolation fallbacks;
- browser profiles cannot overlap journals, workspaces, exports, or Git repositories;
- Windows file locking does not require multiple components to write the same journal directly;
- every AI-assisted change can be inspected, tested, restored, or rejected;
- secrets never enter ordinary logs or repositories;
- the application can safely use AI to improve itself;
- SQL can be added later without redesigning the domain.

---

## 32. Final Design Principle

There are two forms of history:

```text
Communication history
    Every prompt, response, revision, tool result, and intermediate answer.

Workspace history
    Every file state, patch, test result, review, and Git checkpoint.
```

Both histories must be linked.

All authoritative rules are integrated into their owning sections; no later clarification block overrides them.

The design also preserves uncertainty:

```text
unknown provider internals remain opaque
uncertain network paths remain explicitly uncertain
branched context records exactly what was selected
concurrent file changes pause instead of being guessed
```

> Normal AI work preserves every meaningful result. File-changing AI work additionally preserves every iteration as Git history.

Version 12 closes the final known specification-level inconsistencies. Further findings should be treated as implementation issues or explicitly proposed design changes rather than implicit corrections.
