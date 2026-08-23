## Purpose

Enables the parsed text editor on the document review page to correctly load, display, and save content as markdown — so OCR-parsed markdown is rendered with formatting and stored back as valid markdown after user edits.

## ADDED Requirements

### Requirement: Editor loads content as markdown
The editor SHALL parse the incoming `content` prop as markdown and render it with proper formatting (headings, bold, italic, lists, etc.) rather than displaying raw markdown syntax.

#### Scenario: Markdown content is rendered on load
- **WHEN** the editor receives a `content` prop containing markdown syntax (e.g. `# Heading\n**bold**`)
- **THEN** the editor SHALL render the content with visual formatting, not raw syntax characters

#### Scenario: Content update via prop re-renders correctly
- **WHEN** the `content` prop changes to a new markdown string
- **THEN** the editor SHALL update its rendered content to reflect the new markdown

### Requirement: Editor outputs markdown on change
The editor SHALL emit valid markdown string (not plain text or HTML) via the `onChange` callback whenever the user edits the content.

#### Scenario: User edits text and onChange is called
- **WHEN** the user modifies the editor content
- **THEN** `onChange` SHALL be called with the current content serialized as a markdown string

#### Scenario: Formatting applied by user is preserved in output
- **WHEN** the user applies formatting (e.g. bold, heading) using editor controls or markdown shortcuts
- **THEN** `onChange` SHALL emit a markdown string that includes the corresponding markdown syntax for that formatting

### Requirement: Editor respects editable state
The editor SHALL switch between read-only and editable modes based on the `editable` prop, with no change to markdown input/output behavior.

#### Scenario: Editor is in read-only mode
- **WHEN** `editable` is `false`
- **THEN** the editor SHALL render markdown content but not allow user input

#### Scenario: Editor is in editable mode
- **WHEN** `editable` is `true`
- **THEN** the editor SHALL allow the user to type and apply formatting
