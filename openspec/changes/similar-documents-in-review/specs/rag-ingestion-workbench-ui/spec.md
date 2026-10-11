## ADDED Requirements

### Requirement: Document review shows related indexed documents
The document review workbench SHALL render a bounded "Similar documents" section for
related indexed versions returned by the API. It MUST show loading, empty, and recoverable
error states, display each result's title, score, and preview, and link to the result's
document view when an identifier is available.

#### Scenario: Similar documents are found
- **WHEN** the review API returns one or more related indexed versions
- **THEN** the workbench shows the results in descending similarity order with a visible
  score, preview, lifecycle state, and navigation link

#### Scenario: Similar document lookup is unavailable
- **WHEN** the related-document request is still loading, returns no matches, or fails
- **THEN** the workbench communicates the corresponding state without blocking parsed-text
  editing, save, approve, or reject actions
