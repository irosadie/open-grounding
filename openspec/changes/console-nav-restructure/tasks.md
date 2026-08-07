## 1. Config

- [x] 1.1 Rename label "Ingestion" → "Documents" di `console.ts`
- [x] 1.2 Rename label "Retrieval" → "Query" di `console.ts`
- [x] 1.3 Rename label "Settings" → "Configuration" di `console.ts`
- [x] 1.4 Rename label "Model Profiles" → "Models" di `console.ts`
- [x] 1.5 Tambah field `group?: string` ke type `ConsoleNavItem`
- [x] 1.6 Tambah `group: "WORKSPACE"` pada item "Knowledge Bases"
- [x] 1.7 Tambah `group: "SETTINGS"` pada item "Configuration"

## 2. Sidebar Component

- [x] 2.1 Render section divider ketika item memiliki `group` field
- [x] 2.2 Tambah state `settingsOpen` dengan default berdasarkan current path
- [x] 2.3 Item "Configuration" jadi toggle button dengan chevron icon
- [x] 2.4 Sub-items (indent: true) hanya tampil ketika `settingsOpen === true`

## 3. Tests

- [x] 3.1 Update `console-sidebar.test.tsx` dengan label baru

## 4. Verifikasi

- [x] 4.1 Typecheck pass (`bun run typecheck`)
- [x] 4.2 Tests pass (`bun run test`)
- [x] 4.3 Active state bekerja di semua items
- [x] 4.4 Settings section auto-expand saat di `/console/settings/*`
