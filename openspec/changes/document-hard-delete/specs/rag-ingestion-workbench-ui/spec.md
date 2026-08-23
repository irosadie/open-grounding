## ADDED Requirements

### Requirement: Delete button on document list for terminal-state documents
The "Documents in KB" list in the ingestion workbench SHALL show a delete button for each document version in a terminal state (`READY`, `FAILED`, `NEEDS_REVIEW`). The button SHALL trigger a confirmation dialog before calling the delete API.

#### Scenario: Delete button visible for terminal-state documents
- **WHEN** a document version has lifecycle state `READY`, `FAILED`, or `NEEDS_REVIEW`
- **THEN** a delete button is visible in the document row

#### Scenario: Delete button not visible for in-progress documents
- **WHEN** a document version has lifecycle state `PARSING`, `CHUNKING`, `EMBEDDING`, `INDEXING`, `QUEUED`, or `STORED`
- **THEN** no delete button is shown

#### Scenario: Confirmation dialog before delete
- **WHEN** user clicks the delete button
- **THEN** a confirmation dialog appears asking the user to confirm deletion before the API call is made

#### Scenario: Document row shows DELETING state after delete
- **WHEN** the delete API call succeeds
- **THEN** the document row updates to show `DELETING` lifecycle state badge

### Requirement: DELETING and DELETED lifecycle badge in document list
The document list lifecycle badge SHALL handle `DELETING` and `DELETED` states with appropriate label and color.

#### Scenario: DELETING badge shown
- **WHEN** a document version is in `DELETING` state
- **THEN** the badge shows "Deleting" with a gray/neutral color

#### Scenario: DELETED badge shown
- **WHEN** a document version is in `DELETED` state
- **THEN** the badge shows "Deleted" with a muted gray color and the row is visually dimmed
