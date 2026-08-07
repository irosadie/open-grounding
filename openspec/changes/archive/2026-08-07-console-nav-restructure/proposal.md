## Why

Sidebar console saat ini memiliki 11 items datar dengan sub-items yang hanya dibedakan oleh `indent: true`. Tidak ada grouping visual yang jelas, label beberapa item terlalu teknis ("Ingestion", "Retrieval"), dan Settings sub-items selalu terlihat semua tanpa bisa di-collapse. Ini membuat navigasi terasa padat dan membingungkan untuk user baru.

## What Changes

- Rename label yang terlalu teknis menjadi lebih user-friendly
- Kelompokkan Settings sub-items menjadi section collapsible
- Kurangi visual noise dengan grouping yang lebih jelas
- Tidak ada halaman baru, tidak ada route baru — hanya restructure nav config dan sidebar rendering

## Capabilities

### New Capabilities
- `console-nav`: Sidebar navigation dengan grouped sections dan collapsible settings

### Modified Capabilities
- (tidak ada perubahan requirement level pada halaman existing)

## Impact

- `apps/web/configs/console.ts` — restructure nav items dengan grouping
- `apps/web/components/console-sidebar/console-sidebar.tsx` — render grouped nav dengan collapsible settings section
- `apps/web/components/console-sidebar/console-sidebar.test.tsx` — update test sesuai perubahan
