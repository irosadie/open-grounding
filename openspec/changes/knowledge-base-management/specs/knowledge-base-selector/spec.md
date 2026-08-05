## ADDED Requirements

### Requirement: Single knowledge base selector
The system SHALL provide a dropdown selector component that loads the tenant's active knowledge bases and allows selecting one.

#### Scenario: Selector shows available KBs
- **WHEN** user opens the Ingestion form
- **THEN** a dropdown shows all active knowledge bases with their names and slugs

#### Scenario: Selector shows empty state
- **WHEN** tenant has no active knowledge bases
- **THEN** selector shows a message directing user to create a knowledge base first

#### Scenario: Selector disabled while loading
- **WHEN** knowledge base list is being fetched
- **THEN** selector is disabled with a loading indicator

### Requirement: Multi knowledge base selector
The system SHALL provide a multi-select component that allows selecting one or more knowledge bases for retrieval queries.

#### Scenario: Multi-select shows available KBs
- **WHEN** user opens the Retrieval form
- **THEN** a multi-select shows all active knowledge bases

#### Scenario: Selected KBs shown as badges
- **WHEN** user selects one or more knowledge bases
- **THEN** each selected KB is shown as a removable badge

#### Scenario: KB can be deselected
- **WHEN** user clicks the remove button on a selected KB badge
- **THEN** that KB is removed from the selection
