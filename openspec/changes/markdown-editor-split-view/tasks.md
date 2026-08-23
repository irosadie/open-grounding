## 1. Component Restructure

- [ ] 1.1 Add `isSplit` and `isFullscreen` state to `ParsedTextEditor`
- [ ] 1.2 Add toolbar row with split view toggle button (lucide `Columns2` icon)
- [ ] 1.3 Add fullscreen toggle button to toolbar (lucide `Maximize2` / `Minimize2` icon)
- [ ] 1.4 Add Escape key handler to exit fullscreen (`useEffect` + `keydown` listener)

## 2. Split View Layout

- [ ] 2.1 When `isSplit` is false: render existing Tiptap `EditorContent` (single pane, current behavior)
- [ ] 2.2 When `isSplit` is true: render two-column layout (`flex flex-row`)
- [ ] 2.3 Left pane: controlled `<textarea>` bound to `content`, calls `onChange` on change, respects `editable` prop
- [ ] 2.4 Right pane: Tiptap `EditorContent` in read-only mode, synced to `content` via `setContent`
- [ ] 2.5 Add divider between left and right panes

## 3. Fullscreen Layout

- [ ] 3.1 When `isFullscreen` is true: apply `fixed inset-0 z-50 bg-white flex flex-col` to wrapper div
- [ ] 3.2 When `isFullscreen` is false: restore normal inline layout
- [ ] 3.3 In fullscreen mode, editor content area should fill remaining height (`flex-1 overflow-auto`)

## 4. Verify

- [ ] 4.1 Run `bun run typecheck` in `apps/web` — no type errors
- [ ] 4.2 Run `bun run lint` in `apps/web` — no lint errors
- [ ] 4.3 Manually verify: split view toggle switches between single and split pane
- [ ] 4.4 Manually verify: left pane edits update right pane preview in real time
- [ ] 4.5 Manually verify: fullscreen toggle expands editor to full viewport
- [ ] 4.6 Manually verify: Escape key exits fullscreen
- [ ] 4.7 Manually verify: split + fullscreen combination works correctly
