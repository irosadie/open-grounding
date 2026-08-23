## 1. Dependency

- [x] 1.1 Install `@tiptap/extension-markdown` in `apps/web`

## 2. Component Update

- [x] 2.1 Import `Markdown` extension from `@tiptap/extension-markdown` in `parsed-text-editor.tsx`
- [x] 2.2 Register `Markdown` extension in the `extensions` array of `useEditor`
- [x] 2.3 Replace `e.getText()` with `e.storage.markdown.getMarkdown()` in the `onUpdate` callback
- [x] 2.4 Update the `useEffect` content sync to use markdown-aware `setContent` (pass markdown string directly — the extension handles parsing)

## 3. Verify

- [x] 3.1 Run `bun run typecheck` in `apps/web` — no type errors
- [x] 3.2 Run `bun run lint` in `apps/web` — no lint errors
- [ ] 3.3 Manually verify in browser: open a review page, confirm markdown renders with formatting (not raw syntax)
- [ ] 3.4 Manually verify: edit content in the editor, confirm `onChange` emits a markdown string
