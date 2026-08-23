## Why

The document review page (`/console/document/review/[versionId]`) uses Tiptap as its editor, but the parsed content from OCR is stored and transmitted as markdown. The current implementation uses only `StarterKit` with no markdown support — meaning markdown syntax is rendered as raw plain text, and `onChange` outputs unformatted plain text instead of markdown. Users cannot see proper formatting when reviewing or editing OCR-parsed documents.

## What Changes

- Add `@tiptap/extension-markdown` to `apps/web` dependencies
- Update `ParsedTextEditor` to load content from markdown string and output markdown string on change
- Enable markdown-aware toolbar hints (bold, italic, headings) via StarterKit already present
- Remove the raw `getText()` call and replace with `getMarkdown()` from the extension

## Capabilities

### New Capabilities

- `document-review/markdown-editor`: The parsed text editor on the document review page supports markdown input/output — content is parsed from markdown on load and serialized back to markdown on change.

### Modified Capabilities

<!-- None — no existing spec-level behavior changes outside the editor component -->

## Impact

- **`apps/web/package.json`** — add `@tiptap/extension-markdown`
- **`apps/web/app/console/document/review/[versionId]/_components/parsed-text-editor.tsx`** — integrate markdown extension, fix `onChange` to emit markdown
- No API contract changes, no backend changes, no shared package changes
