# Design: Console Nav Restructure

## Current State

```
Overview
Knowledge Bases
Ingestion
Retrieval
Memory
Settings
  Model Profiles      (indent)
  Index Profiles      (indent)
  Confidence          (indent)
  Providers           (indent)
  MCP Servers         (indent)
```

11 items, flat, settings sub-items selalu visible.

## Proposed Structure

```
Overview

── WORKSPACE ──
Knowledge Bases
Documents           (rename: Ingestion)
Query               (rename: Retrieval)
Memory

── SETTINGS ──
Configuration       (rename: Settings — section header)
  Models            (rename: Model Profiles)
  Index Profiles
  Confidence
  Providers
  MCP Servers
```

### Label Changes
| Sebelum | Sesudah | Alasan |
|---|---|---|
| Ingestion | Documents | Lebih familiar, menggambarkan konten bukan proses |
| Retrieval | Query | Lebih natural untuk end user |
| Settings | Configuration | Lebih deskriptif |
| Model Profiles | Models | Lebih ringkas |

### Collapsible Settings
- Settings section punya toggle chevron
- Default: expanded jika current path adalah `/console/settings/*`, collapsed jika tidak
- State disimpan di `useState` lokal (tidak perlu persist)

## Data Structure Changes

`ConsoleNavItem` perlu support `group` label untuk section divider:

```ts
export type ConsoleNavItem = {
  label: string
  href: string
  icon: typeof Database
  description: string
  indent?: boolean
  group?: string   // section label sebelum item ini
}
```

## Component Changes

### `console.ts`
- Rename labels sesuai tabel di atas
- Tambah `group` field pada item pertama setiap section

### `console-sidebar.tsx`
- Render `group` label sebagai section divider (uppercase, small, muted)
- Settings sub-items dalam collapsible group
- Chevron toggle untuk settings section
- Auto-expand jika active path ada di settings

## Visual

```
┌─────────────────────┐
│ ⊞ Overview          │
│                     │
│ WORKSPACE           │
│ 🗄 Knowledge Bases  │
│ 📄 Documents        │
│ 🔍 Query            │
│ 🧠 Memory           │
│                     │
│ SETTINGS            │
│ ⚙ Configuration  ▾ │
│   🖥 Models         │
│   📋 Index Profiles │
│   📊 Confidence     │
│   🔑 Providers      │
│   🔌 MCP Servers    │
└─────────────────────┘
```
