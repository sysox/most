# MCP operation identity contract

When a Tandem stage has an `operation_id`, MOST forwards it to configured
MCP HTTP servers as:

```text
X-Tandem-Operation-Id: <operation_id>
```

The same value is reused for bounded retries of one stage. A rewind creates a
new pipeline branch and therefore a new operation identity.

This header is an idempotency key, not a guarantee by itself. An MCP server
that performs external side effects must store the key with its result and
return the original result for duplicate requests. Servers must treat an
unknown or missing header as a normal non-idempotent request.

Standalone MOST CLI sessions omit the header. OpenCode and Claude remote MCP
configurations use the same contract.
