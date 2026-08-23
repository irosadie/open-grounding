# kb-detail-shell Specification

## Purpose
A Knowledge Base detail layout with persistent tab navigation that wraps all
per-KB configuration surfaces (Planner, Memory, Decomposition, Ingestion Settings)
under a single entry point. Replaces the scattered action-button pattern on the KB
list page with a cohesive detail page experience.

## Requirements

### Requirement: KB detail layout provides persistent tab navigation
The system SHALL render a shared layout at `/console/knowledge-bases/[id]/` that
displays the KB name, status, and a tab bar with tabs for each configuration surface.
The active tab MUST be derived from the current route segment, not local state.

#### Scenario: User navigates between tabs
- **WHEN** a user clicks a tab in the KB detail layout
- **THEN** the URL changes to the corresponding sub-route and the active tab indicator
  updates without a full page reload

#### Scenario: User opens a direct deep link to a tab
- **WHEN** a user navigates directly to `/console/knowledge-bases/{id}/ingestion`
- **THEN** the layout renders with the correct tab active and the tab content loaded

### Requirement: Tab shell exposes all four configuration surfaces
The KB detail layout SHALL include tabs for: Planner, Memory, Decomposition, and
Ingestion Settings — in that order. Each tab MUST link to its corresponding
existing or new sub-route.

#### Scenario: All tabs are visible
- **WHEN** a user opens any KB detail page
- **THEN** all four tabs (Planner, Memory, Decomposition, Ingestion Settings) are visible
  and navigable regardless of which tab is currently active

### Requirement: KB list page uses a single entry point per KB
The KB list page SHALL replace per-KB action buttons (Planner, Memory) with a single
"Open" or clickable KB name that navigates to the KB detail layout. Individual config
surface buttons MUST NOT appear on the list page.

#### Scenario: User opens a KB from the list
- **WHEN** a user clicks on a KB entry or its "Open" button on the list page
- **THEN** the user is navigated to `/console/knowledge-bases/{id}/planner` as the
  default landing tab

### Requirement: Layout displays KB identity as read-only header
The KB detail layout SHALL display the KB name and lifecycle status in a persistent
header above the tab bar. This header MUST be derived from the server-returned KB
record and MUST NOT allow inline editing.

#### Scenario: User views KB detail
- **WHEN** a user opens any KB detail tab
- **THEN** the KB name and status badge are visible in the layout header above the tabs
