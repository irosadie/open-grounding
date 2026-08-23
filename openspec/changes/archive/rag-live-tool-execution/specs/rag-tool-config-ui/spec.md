# rag-tool-config-ui Specification (delta)

## Purpose
Provide operators a console UI under `/console/settings/tools` to manage tool
definitions, grant/revoke per-tenant permissions, and inspect the audit trail — all
within the existing console shell and settings navigation pattern.

## ADDED Requirements

### Requirement: Operators can register and manage tool definitions from the console
The system SHALL provide a settings page at `/console/settings/tools` where operators
can view active tool definitions for their tenant, register a new tool definition
(slug, adapter, JSON Schema), and deactivate an existing tool. The page MUST follow
the established `PanelCard` + inline form pattern used by model and index profile pages.

#### Scenario: Operator registers a new tool
- **WHEN** an operator fills in the inline tool registration form and submits
- **THEN** the form validates required fields (slug, adapter, input schema, output
  schema) client-side with Zod before calling the API, shows an inline error on
  validation failure, and refreshes the tool list on success

#### Scenario: No tools are registered yet
- **WHEN** the tools page loads and the tenant has no active tool definitions
- **THEN** the page displays an `EmptyState` component with a prompt to register the
  first tool

### Requirement: Operators can grant and revoke tool permissions from the console
The system SHALL provide a permission management section on the tools page where
operators can see which tools are permitted, grant permission to an active tool, and
revoke a previously granted permission. Revocation MUST use the inline two-button
confirm pattern (Revoke + Cancel) without a modal.

#### Scenario: Operator grants permission to a tool
- **WHEN** an operator clicks Grant on an active tool that has no current permission
- **THEN** the system calls the grant endpoint, shows a success state, and the tool
  moves to the permitted list

#### Scenario: Operator revokes a tool permission
- **WHEN** an operator initiates revocation and confirms in the inline confirm UI
- **THEN** the system calls the revoke endpoint, the permission record is marked
  revoked, and the tool moves back to the unpermitted list

### Requirement: Operators can inspect the tool audit log from the console
The system SHALL provide a paginated audit log view on the tools page showing recent
tool invocations for the tenant. Each row SHALL display: tool slug, status badge
(SUCCESS / TIMEOUT / ERROR / DENIED), latency_ms, and created_at. Raw input and output
MUST NOT be displayed. The view MUST be read-only.

#### Scenario: Operator inspects a DENIED audit entry
- **WHEN** an operator views the audit log and a DENIED entry is present
- **THEN** the row shows the tool slug, a DENIED status badge in danger color, and
  the timestamp without exposing any input content

### Requirement: Tool config UI follows existing console patterns exactly
The system SHALL implement the tools settings page using the same conventions as
`models-content.tsx` and `index-profiles-content.tsx`: `"use client"` content
component, `PanelCard` containers, inline toggled form with plain controlled inputs
and Zod `safeParse` validation, `useMutation` with `onSuccess` invalidation, native
`<select>` for enum fields, no react-hook-form, no dialog/drawer components.

#### Scenario: Tool page loads with existing tools
- **WHEN** an operator navigates to `/console/settings/tools`
- **THEN** the page renders within the console sidebar layout, shows the tools list
  in a `PanelCard`, and the sidebar highlights the Tools nav item as active
