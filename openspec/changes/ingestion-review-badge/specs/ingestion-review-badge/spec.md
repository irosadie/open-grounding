## ADDED Requirements

### Requirement: Badge counter surfaces documents awaiting human review in sidebar
The system SHALL provide a mechanism for the console UI to know how many documents
are currently in `NEEDS_REVIEW` state for the active tenant, so the sidebar can
surface this count as a badge on the Documents navigation item without requiring
the user to navigate into the ingestion page first.

#### Scenario: User sees badge on Documents menu
- **WHEN** one or more documents are in `NEEDS_REVIEW` state
- **THEN** the Documents menu item in the sidebar shows a red numeric badge

#### Scenario: Badge disappears after all reviews are done
- **WHEN** all documents in `NEEDS_REVIEW` have been approved or rejected
- **THEN** the badge is no longer shown on the Documents menu item

#### Scenario: Badge is not shown to unauthenticated users
- **WHEN** the sidebar is rendered without a valid tenant session
- **THEN** no badge is shown and no count request is made
