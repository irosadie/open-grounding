# Answer policy and guardrails operations

Answer behavior is tenant-scoped and versioned. The effective query policy is loaded
from the deployment default and an optional knowledge-base override. A missing active
policy is an operational failure; the query path does not silently select a permissive
code default.

## Configuration

Use the Answer Policy tab on a knowledge base or the following API surfaces:

- `GET /rag/knowledge-bases/{id}/effective-answer-policy` — read-only effective merge;
- `GET/POST/DELETE /rag/knowledge-bases/{id}/answer-behavior` — local answer behavior;
- `GET /rag/knowledge-bases/{id}/answer-behavior/defaults` — migrated defaults;
- `GET/POST/DELETE /rag/knowledge-bases/{id}/guardrails` — local guardrail additions.

Only tenant ADMIN users can write or retire local policy versions. Saving creates a new
immutable version and retires the previous active local version. Removing an override
returns the knowledge base to the inherited deployment policy. The effective response
contains safe version and budget metadata; it never contains provider credentials or
tool arguments.

## Source policy

- `DOCUMENT_ONLY`: selected authorized document citations are required.
- `DOCUMENT_OR_MCP`: selected document or validated, fresh MCP citations are required.
- `DOCUMENT_MCP_GENERAL`: general answers are allowed only when the configured fallback
  permits them; they are returned as non-grounded and have no fabricated citations.

MCP citations are labeled `MCP` and include only server, tool, invocation, trace, and
freshness metadata. Tool text remains untrusted source data.

## Safe rollout and rollback

1. Validate the policy in a non-production knowledge base with grounded, no-evidence,
   greeting, prompt-injection, provider-failure, and MCP freshness cases.
2. Confirm the effective policy version and output budget in the answer trace.
3. If a version is unsafe, remove the local override to inherit the deployment default,
   or create a new validated version from the last known-good values. Historical rows
   and audit records are retained for investigation.

Policy audit entries contain stage, version, decision, stable reason, and trace ID only.
Raw prompts, credentials, hidden reasoning, and raw MCP arguments are excluded.
