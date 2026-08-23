## Purpose

Allows reviewers to expand the parsed text editor to fill the full viewport, providing more space for reviewing and editing long OCR-parsed documents.

## ADDED Requirements

### Requirement: Editor has a fullscreen toggle button
The editor header SHALL display a toggle button that switches between normal and fullscreen modes.

#### Scenario: Default state is normal mode
- **WHEN** the editor first renders
- **THEN** it SHALL display in normal (inline) mode

#### Scenario: User activates fullscreen
- **WHEN** the user clicks the fullscreen toggle button
- **THEN** the editor SHALL expand to cover the full viewport, overlaying the page

#### Scenario: User deactivates fullscreen
- **WHEN** the user clicks the fullscreen toggle button while in fullscreen mode
- **THEN** the editor SHALL return to normal inline mode

### Requirement: Fullscreen mode preserves split view state
Entering or exiting fullscreen mode SHALL NOT change the current split view state.

#### Scenario: Split view preserved in fullscreen
- **WHEN** split view is active and the user activates fullscreen
- **THEN** the editor SHALL show split view in fullscreen

#### Scenario: Single pane preserved in fullscreen
- **WHEN** split view is inactive and the user activates fullscreen
- **THEN** the editor SHALL show single pane in fullscreen

### Requirement: Fullscreen can be dismissed with Escape key
The editor SHALL exit fullscreen mode when the user presses the Escape key.

#### Scenario: Escape exits fullscreen
- **WHEN** the editor is in fullscreen mode and the user presses Escape
- **THEN** the editor SHALL exit fullscreen mode
