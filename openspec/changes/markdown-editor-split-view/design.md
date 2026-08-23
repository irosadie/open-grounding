## Context

`ParsedTextEditor` is a single-file Tiptap-based editor component. It already has `@tiptap/markdown` integrated (from the previous change). The component receives `content` (markdown string), `editable` (bool), and `onChange` callback. It has no toolbar or layout chrome today.

The page layout (`review-content.tsx`) has a fixed action bar at the bottom. The editor sits inside a `PanelCard` with constrained width (`max-w-4xl`).

## Goals / Non-Goals

**Goals:**
- Add a toolbar row above the editor with split view + fullscreen toggle buttons
- Split view: left = raw markdown textarea, right = Tiptap WYSIWYG preview (read-only)
- Fullscreen: `position: fixed; inset: 0` overlay with high z-index
- Escape key exits fullscreen
- Both modes composable (split + fullscreen works together)
- Zero new dependencies — use lucide-react (already installed) for icons, Tailwind for layout

**Non-Goals:**
- Syntax highlighting in the raw markdown pane
- Toolbar formatting buttons (bold, italic, etc.)
- Persisting split/fullscreen preference across sessions

## Decisions

### Split view implementation: textarea + Tiptap read-only instance

**Chosen:** Left pane = plain `<textarea>` (controlled, synced to `content` state). Right pane = existing Tiptap `EditorContent` in read-only mode.

**Rationale:**
- Textarea for raw markdown is the simplest, most reliable approach — no extra Tiptap instance needed for the editable side
- In split mode, the textarea is the source of truth; `onChange` is called from textarea `onChange`
- In single-pane mode, revert to current Tiptap WYSIWYG behavior
- Right pane Tiptap instance is always `editable: false`, receives content updates via `setContent`

**Alternatives considered:**
- Two Tiptap instances (both sides) — more complex sync, higher overhead
- CodeMirror for left pane — adds a dependency

### Fullscreen: CSS `position: fixed` with `z-50`

**Chosen:** Toggle a `isFullscreen` state that applies `fixed inset-0 z-50 bg-white flex flex-col` to the wrapper div.

**Rationale:**
- No Portal needed — `position: fixed` takes the element out of normal flow regardless of DOM position
- Simple toggle, easy to reverse
- Works with existing Tailwind classes

### Toolbar layout

Single row above the editor content area:
```
[ Split View icon ]  [ Fullscreen icon ]   ← right-aligned
```
Icons from lucide-react: `Columns2` for split view, `Maximize2` / `Minimize2` for fullscreen. Active state indicated by a filled/highlighted icon background.

## Risks / Trade-offs

- **Textarea ↔ Tiptap sync in split mode** — textarea value and Tiptap content must stay in sync. In split mode `onChange` fires from textarea, so Tiptap right pane just receives the new markdown as prop. Simple one-way flow.
- **Fullscreen over action bar** — when fullscreen, the sticky `ReviewActionBar` at the bottom of the page will be hidden behind the editor overlay. This is acceptable — the action bar buttons (Save, Approve, Reject) are not needed while in fullscreen editing mode. User exits fullscreen first, then acts.
