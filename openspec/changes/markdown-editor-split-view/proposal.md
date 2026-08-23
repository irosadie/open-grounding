## Why

The document review page's parsed text editor is a single-pane WYSIWYG editor with no way to see raw markdown or switch to a focused full-screen mode. Reviewers correcting OCR-parsed documents need to:
1. See raw markdown alongside the rendered preview to verify formatting accuracy
2. Expand the editor to full screen for documents with long content

## What Changes

- Add a **split view toggle** to `ParsedTextEditor` — left pane shows raw markdown (plain textarea), right pane shows live rendered preview
- Add a **full screen toggle** — editor expands to cover the full viewport, with the same split/single view preserved
- Default state: single pane (current WYSIWYG), split view off, full screen off
- Both toggles are icon buttons inside the editor toolbar area

## Capabilities

### New Capabilities

- `document-review/editor-split-view`: The parsed text editor supports a split view mode with a raw markdown pane on the left and a live rendered preview on the right, toggled by a button in the editor header.
- `document-review/editor-fullscreen`: The parsed text editor supports a full screen mode that expands the editor to fill the viewport, toggled by a button in the editor header.

### Modified Capabilities

<!-- None -->

## Impact

- **`apps/web/app/console/document/review/[versionId]/_components/parsed-text-editor.tsx`** — add toolbar with split view + fullscreen toggle buttons, split pane layout
- No API contract changes, no backend changes, no shared package changes
- New dependency: none (use existing Tailwind, lucide-react already installed)
