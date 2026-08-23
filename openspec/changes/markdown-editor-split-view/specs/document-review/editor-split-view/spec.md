## Purpose

Allows reviewers to see raw markdown and rendered preview side-by-side in the parsed text editor, so they can verify and correct OCR-parsed formatting accurately.

## ADDED Requirements

### Requirement: Editor has a split view toggle button
The editor header SHALL display a toggle button that switches between single-pane and split-view modes.

#### Scenario: Default state is single pane
- **WHEN** the editor first renders
- **THEN** it SHALL display in single-pane mode (no split view)

#### Scenario: User activates split view
- **WHEN** the user clicks the split view toggle button
- **THEN** the editor SHALL switch to split-view mode with raw markdown on the left and rendered preview on the right

#### Scenario: User deactivates split view
- **WHEN** the user clicks the split view toggle button while in split-view mode
- **THEN** the editor SHALL return to single-pane mode

### Requirement: Split view left pane shows raw markdown
The left pane in split-view mode SHALL display the raw markdown string as plain editable text (textarea).

#### Scenario: Left pane reflects current content
- **WHEN** split view is active
- **THEN** the left pane SHALL show the current markdown string

#### Scenario: Edits in left pane update the right pane
- **WHEN** the user edits text in the left pane
- **THEN** the right pane SHALL update its rendered preview in real time

### Requirement: Split view right pane shows rendered preview
The right pane in split-view mode SHALL display the markdown rendered as formatted HTML (read-only).

#### Scenario: Right pane renders markdown formatting
- **WHEN** split view is active and the content contains markdown syntax
- **THEN** the right pane SHALL render headings, bold, italic, lists, etc. visually

#### Scenario: Right pane is not editable
- **WHEN** split view is active
- **THEN** the right pane SHALL be read-only and not accept user input

### Requirement: Split view respects editable state
In split-view mode, the left pane SHALL only be editable when the `editable` prop is `true`.

#### Scenario: Non-editable split view
- **WHEN** `editable` is `false` and split view is active
- **THEN** the left pane SHALL be read-only
