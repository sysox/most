# Implementation Issues and TODOs

## Repository Issues

- [x] Add the application source tree. Initial Python safety-kernel package is present under `most/`.
- [x] Choose and document the implementation language and framework. Python with `uv`, setuptools, PyYAML, and cryptography is documented in `pyproject.toml` and `README.md`.
- [x] Add dependency and build manifests. `pyproject.toml` and `uv.lock` are present.
- [ ] Add configuration schemas and serialization code.
- [x] Add automated tests and test configuration. `tests/` and pytest configuration are present.
- [x] Expand `README.md` with setup, development, and usage instructions.
- [x] Add repository ignore rules, including protection for secrets, browser profiles, journals, artifacts, and generated files.

## Design Decisions to Resolve

- [x] Define how the resulting Git commit hash is linked back into journal metadata. Resolved by the two-phase commit-linkage protocol in `design.md` §18.5 and §21.
- [x] Define whether session-level `events.jsonl` from `design.md` §16 is authoritative or a derived copy of execution-level `events.jsonl` from §15. Resolved as a derived session projection in `design.md` §10.2 and §16.
- [x] Reconcile mandatory preservation of intermediate results in §2.1 with the ability to disable intermediate-result logging in `LoggingPolicy` (§7.8). Resolved by requiring linkage metadata and explicit redaction records while allowing sensitive payload omission in `design.md` §16.
- [x] Define whether `PersistenceCoordinator` controls only application-data writes or also workspace and Git file mutations (§14.14, §21.1). Resolved in `design.md` §14.14: workspace and Git mutations remain under `WorkspaceService` and `GitService`.
- [x] Define how persisted-record headers apply to Markdown result files (§7.9, §15–§16). Resolved in `design.md` §7.9: owning structured metadata records carry the headers.
- [ ] Select the initial UI and CLI technology; the architecture lists several interfaces but does not choose an MVP implementation.
- [x] Define the canonical location and synchronization rules for workspace journals (§15, §18.1, §19). Resolved in `design.md` §24: application data is authoritative and project-local journals are synchronized exports unless explicitly configured otherwise.
- [x] Clarify whether checkpoint commits are mandatory by default or optional according to policy (§18.4, §18.9, §25). Resolved in `design.md` §18.4: one checkpoint per meaningful iteration unless `MANUAL` is selected.
- [ ] Define credential-handle lifetime, memory handling, redaction, and adapter access rules (§7.6, §12.1).
- [ ] Define the exact schema and ownership of derived indexes under `indexes/` (§15, §21).

## Core Implementation TODOs

- [ ] Implement canonical IDs, UTC timestamps, enums, nullable fields, metadata, and references (§7.9).
- [ ] Implement persisted-record headers, schema dispatch, tolerant readers, strict writers, migrations, and compatibility fixtures (§7.9, §30).
- [ ] Implement `AIProvider`, `AIModel`, `AIConfiguration`, `AccessMethod`, policies, capabilities, and `ApplicationSettings` (§7).
- [ ] Implement configuration precedence for exposure, context overflow, and workspace context policies (§7.3).
- [ ] Implement sessions, immutable session modes, interactions, result trees, branching, and final-result selection (§8).
- [ ] Implement requests, messages, content parts, responses, attachments, and usage/cost records (§9).
- [ ] Implement deterministic branch-to-context assembly and persist `ContextAssemblyRecord` (§9.5).
- [ ] Implement shared context-budget estimation and explicit overflow policies without silent trimming or truncation (§9.5).
- [ ] Implement the execution lifecycle and validate all allowed state transitions (§10).
- [ ] Implement execution steps, stream events, event ordering, and optional hash chaining (§10.1–§10.2).
- [ ] Implement declared, discovered, restricted, and effective capabilities (§11).

## Adapter and Safety TODOs

- [ ] Implement `AdapterExecutionContext` and enforce immutable execution snapshots (§12.1).
- [ ] Implement `AdapterRegistry` and adapter validation, connection testing, capabilities, observability, execution, streaming, and cancellation (§12, §14.2).
- [ ] Implement the OpenAI-compatible adapter required by the MVP (§25).
- [ ] Implement one official cloud API adapter required by the MVP (§25).
- [ ] Implement the generic CLI adapter with redacted command capture and conservative observability (§13.1).
- [ ] Implement the browser adapter with versioned selector packs, failure diagnostics, bounded recovery, and explicit pauses (§13.2).
- [ ] Implement native or encrypted secret stores and ensure secrets never enter YAML, JSON, JSONL, Markdown, logs, or Git (§7.6, §23).
- [ ] Implement connectivity resolution with `VERIFIED`, `INFERRED`, `DECLARED`, and `UNKNOWN` confidence states (§13.3).
- [ ] Block or explicitly confirm exposure-increasing transitions before protected content is transmitted (§14.5).
- [ ] Treat unknown connectivity as unsafe by default (§13.3, §23).
- [ ] Implement isolated browser-profile roots and reject path overlap with journals, workspaces, repositories, and exports (§13.2).
- [ ] Implement POSIX process-group/session isolation and Windows Job Object isolation (§13.1).
- [ ] Implement complete descendant-tree cancellation, grace periods, forced termination, and post-cancellation workspace scans (§13.1).

## Persistence and Recovery TODOs

- [ ] Implement repository interfaces and file-backed repositories listed in `design.md` §15.
- [ ] Implement atomic temporary-file replacement for snapshots and derived documents (§21).
- [ ] Implement append-only JSONL event writing with bounded flushes and closed file handles (§21.1).
- [ ] Ignore one incomplete final JSONL line during crash recovery (§21.1).
- [ ] Preserve incomplete executions and write explicit completion markers (§21).
- [ ] Implement content-addressed artifact storage and hash verification (§20).
- [ ] Implement one `PersistenceCoordinator` writer for each application-data root (§14.14, §21.1).
- [ ] Implement data-root leases, heartbeats, stale-process checks, safe takeover, and recovery audit events (§21.1).
- [ ] Implement bounded retry/backoff for Windows sharing and antivirus/indexer locks (§21.1).
- [ ] Make indexes fully rebuildable from authoritative files (§21).

## Workspace and Git TODOs

- [ ] Require Git for every file-changing AI session (§2.2, §18).
- [ ] Prevent AI changes directly on the main branch (§22, §23).
- [ ] Implement dirty-tree inspection and the configured policies `REQUIRE_CLEAN`, `ISOLATE_FROM_HEAD`, `IMPORT_USER_SNAPSHOT`, and `STASH_WITH_CONFIRMATION` (§18.6).
- [ ] Implement dedicated branches and worktrees with the documented fallback chain (§18.2, §18.7).
- [ ] Inspect and handle submodules, Git LFS, filesystem permissions, and Windows path limits (§18.7).
- [ ] Implement recoverable workspace leases and one active writer per AI worktree (§18.8).
- [ ] Detect unexpected file hashes or Git-state changes and pause with `WORKSPACE_DIVERGED` (§18.8).
- [ ] Implement the `AIIteration` record and store plans, patches, commands, tests, reviews, diffs, and commit references (§18.3, §19).
- [ ] Create checkpoint commits for meaningful iterations and include session/iteration metadata (§18.4).
- [ ] Link each checkpoint bidirectionally to the exact AI request and execution (§18.5).
- [ ] Require explicit approval for merge, squash, history rewrite, destructive recovery, and finalization (§18.9, §23).
- [ ] Implement restore, compare, export, reject, and workspace-session finalization flows (§18.9).

## Testing and Validation TODOs

- [ ] Add unit tests for schemas, migrations, policy precedence, state transitions, and context assembly.
- [ ] Add persistence crash-recovery and partial-JSONL tests.
- [ ] Add secret-redaction and path-isolation tests.
- [ ] Add connectivity and exposure-policy tests for local, private, public, redirected, and unknown endpoints.
- [ ] Add process-tree cancellation tests on POSIX and Windows.
- [ ] Add temporary-repository tests for dirty worktrees, branches, worktrees, submodules, LFS, divergence, leases, and checkpoint linkage.
- [ ] Add fake-adapter tests for all observability profiles without fabricating hidden activity.
- [ ] Add artifact hashing and deduplication tests.
- [ ] Add cross-platform CI for macOS, Linux, and Windows (§1, §6, §31).
- [ ] Define and document the final test, lint, type-check, build, and packaging commands after the technology stack is selected.

## Suggested Validation Commands After Tooling Exists

```bash
git status --short --branch
git diff --check
<project-test-command>
<project-lint-command>
<project-type-check-command>
<project-build-command>
```
