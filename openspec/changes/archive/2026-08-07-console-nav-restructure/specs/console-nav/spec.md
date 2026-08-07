# Spec: Console Nav

## Capability

Sidebar navigation console dengan grouped sections, label user-friendly, dan collapsible settings.

## Requirements

### REQ-1: Label rename
- "Ingestion" → "Documents"
- "Retrieval" → "Query"
- "Settings" → "Configuration"
- "Model Profiles" → "Models"

### REQ-2: Section dividers
`ConsoleNavItem` mendukung field opsional `group?: string`. Jika ada, sidebar merender section label sebelum item tersebut. Section label: uppercase, text-xs, text muted, tidak clickable.

### REQ-3: Collapsible settings section
- Settings sub-items (indent: true) dirender dalam collapsible group
- Default collapsed jika current path tidak dimulai dengan `/console/settings`
- Default expanded jika current path dimulai dengan `/console/settings`
- Toggle via klik pada item "Configuration"
- Chevron icon menunjukkan state (down = collapsed, up = expanded)

### REQ-4: Active state tetap berfungsi
Item nav yang aktif tetap mendapat highlight style yang sama seperti sebelumnya.

### REQ-5: Mobile behavior tidak berubah
`onNavClick` callback tetap dipanggil saat item diklik di mobile.

### REQ-6: Test diupdate
`console-sidebar.test.tsx` diupdate sesuai label baru.

## Out of Scope
- Perubahan route/URL
- Perubahan halaman existing
- Persist collapse state ke localStorage
- Animasi collapse/expand
