## Context

`ParsedTextEditor` (`apps/web/app/console/document/review/[versionId]/_components/parsed-text-editor.tsx`) uses Tiptap v3 with only `StarterKit`. The component receives a markdown string as `content` and emits plain text via `e.getText()` on change. There is no markdown parsing on input or markdown serialization on output — raw markdown syntax is shown as-is in the editor.

Tiptap v3 is already installed (`@tiptap/react ^3.20.1`, `@tiptap/starter-kit ^3.20.1`). The official `@tiptap/extension-markdown` supports Tiptap v3 and provides both markdown-to-document parsing and document-to-markdown serialization.

## Goals / Non-Goals

**Goals:**
- Editor renders markdown content with visual formatting on load
- `onChange` emits a markdown string (not plain text or HTML)
- Behavior of `editable` prop is unchanged
- Minimal diff — only touch `parsed-text-editor.tsx` and `package.json`

**Non-Goals:**
- Adding a toolbar UI or formatting buttons
- Supporting MDX, LaTeX, or custom syntax
- Changing the API contract (`onChange: (text: string) => void` signature stays the same)
- Any backend changes

## Decisions

### Use `@tiptap/extension-markdown` over custom solution

**Chosen:** Add `@tiptap/extension-markdown` as a Tiptap extension.

**Rationale:**
- Official extension, maintained by the Tiptap team, compatible with v3
- Handles both directions: markdown string → Tiptap document (on load) and Tiptap document → markdown string (on `getMarkdown()`)
- Zero custom parsing code needed
- Works with existing `StarterKit` extensions (headings, bold, italic, lists, code)

**Alternatives considered:**
- `remark` / `unified` for manual parsing — adds two more dependencies and requires bridging Tiptap's internal ProseMirror schema manually
- `marked` for render-only — only solves the display side, not the serialization side

### Keep `onChange` signature unchanged

`onChange: (text: string) => void` stays the same. The caller (`review-content.tsx`) uses the string to track dirty state and submit to the API — it doesn't care whether the string is plain text or markdown as long as it's a string. Switching from `getText()` to `getMarkdown()` is transparent to the caller.

## Risks / Trade-offs

- **Markdown round-trip fidelity** — Some markdown constructs may not survive a parse → edit → serialize cycle perfectly (e.g. unusual whitespace, HTML blocks). For OCR-parsed content this is acceptable; the user is already correcting the text.
  → Mitigation: none needed for this use case; document it as a known trade-off.

- **Bundle size** — `@tiptap/extension-markdown` adds ~10 KB gzipped.
  → Acceptable; Tiptap is already in the bundle.

## Migration Plan

1. Install `@tiptap/extension-markdown` in `apps/web`
2. Update `ParsedTextEditor` to import and register the extension
3. Replace `e.getText()` with `e.storage.markdown.getMarkdown()` in `onUpdate`
4. Replace `editor.commands.setContent(content)` with markdown-aware content set
5. No rollback complexity — change is isolated to one component file
