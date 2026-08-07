## ADDED Requirements

### Requirement: Sidebar displays badge for documents pending review
The console sidebar SHALL display a numeric badge on the "Documents" navigation item
when there are document versions in `NEEDS_REVIEW` state for the active tenant.
The badge MUST show the exact count. The badge MUST NOT be shown when the count is zero.
The count MUST be refreshed automatically at a reasonable interval.

#### Scenario: Documents pending review exist
- **WHEN** the sidebar renders and there are one or more documents in `NEEDS_REVIEW` state
- **THEN** the "Documents" nav item displays a red numeric badge with the count

#### Scenario: No documents pending review
- **WHEN** the sidebar renders and there are no documents in `NEEDS_REVIEW` state
- **THEN** the "Documents" nav item displays no badge

#### Scenario: Count changes while sidebar is open
- **WHEN** a document transitions out of `NEEDS_REVIEW` (approved or rejected) while the sidebar is open
- **THEN** the badge count updates within the configured polling interval
