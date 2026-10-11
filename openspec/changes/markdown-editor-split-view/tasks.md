## 1. Component Restructure

- [x] 1.1 Add `isSplit` and `isFullscreen` state to `ParsedTextEditor`
- [x] 1.2 Add toolbar row with split view toggle button (lucide `Columns2` icon)
- [x] 1.3 Add fullscreen toggle button to toolbar (lucide `Maximize2` / `Minimize2` icon)
- [x] 1.4 Add Escape key handler to exit fullscreen (`useEffect` + `keydown` listener)

## 2. Split View Layout

- [x] 2.1 When `isSplit` is false: render existing Tiptap `EditorContent` (single pane, current behavior)
- [x] 2.2 When `isSplit` is true: render two-column layout (`flex flex-row`)
- [x] 2.3 Left pane: controlled `<textarea>` bound to `content`, calls `onChange` on change, respects `editable` prop
- [x] 2.4 Right pane: Tiptap `EditorContent` in read-only mode, synced to `content` via `setContent`
- [x] 2.5 Add divider between left and right panes

## 3. Fullscreen Layout

- [x] 3.1 When `isFullscreen` is true: apply `fixed inset-0 z-50 bg-white flex flex-col` to wrapper div
- [x] 3.2 When `isFullscreen` is false: restore normal inline layout
- [x] 3.3 In fullscreen mode, editor content area should fill remaining height (`flex-1 overflow-auto`)

## 4. Verify

- [x] 4.1 Run `bun run typecheck` in `apps/web` — no type errors
- [x] 4.2 Run `bun run lint` in `apps/web` — no lint errors
- [x] 4.3 Verify: split view toggle switches between single and split pane
- [x] 4.4 Verify: left pane edits update right pane preview in real time
- [x] 4.5 Verify: fullscreen toggle expands editor to full viewport
- [x] 4.6 Verify: Escape key exits fullscreen
- [x] 4.7 Verify: split + fullscreen combination works correctly

## Verification notes

- Component tests cover split toggling, markdown preview synchronization, read-only mode, fullscreen layout, Escape dismissal, and body scroll restoration.
- `bun run typecheck`, `bun run lint`, and the complete frontend test suite pass.
