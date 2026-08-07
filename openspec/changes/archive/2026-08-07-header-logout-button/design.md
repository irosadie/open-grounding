# Design: Header Logout Button

## Overview

`UserMenu` saat ini punya dua mode:
- **Normal** (sidebar): avatar + nama + email + chevron, dropdown muncul ke `bottom-full` (atas)
- **Collapsed** (topbar): hanya inisial avatar, dropdown muncul ke `bottom-full left-1/2` (atas-tengah)

Masalah: topbar ada di bagian **atas** halaman, jadi dropdown harusnya muncul ke **bawah**, bukan ke atas.

## Solution

Tambah prop `dropdownPosition?: "top" | "bottom"` ke `UserMenu`. Default `"top"` (existing behavior untuk sidebar). Topbar akan pass `dropdownPosition="bottom"`.

Tidak perlu buat komponen baru — minimum touch pada `UserMenu` yang sudah ada.

## Component Changes

### `UserMenu` (`apps/web/components/user-menu/user-menu.tsx`)

Tambah prop:
```ts
interface UserMenuProps {
  collapsed?: boolean
  dropdownPosition?: "top" | "bottom"
}
```

Collapsed mode dropdown position:
- `"top"` (default): `bottom-full left-1/2 -translate-x-1/2 mb-2` (existing)
- `"bottom"`: `top-full right-0 mt-2`

### `ConsoleTopbar` (`apps/web/components/console-topbar/console-topbar.tsx`)

```tsx
<UserMenu collapsed dropdownPosition="bottom" />
```

## Visual Behavior

```
┌─────────────────────────────────────────┐
│ Open Grounding Console  / Settings      │
│                              [Avatar] ← │
└─────────────────────────────────────────┘
                               ┌─────────┐
                               │ Imron   │
                               │ imron@  │
                               ├─────────┤
                               │ Logout  │
                               └─────────┘
```

Dropdown muncul ke bawah-kanan dari avatar, aligned ke kanan (`right-0`).

## No Changes Needed

- Sidebar `UserMenu` — tidak berubah, tetap pakai default `dropdownPosition="top"`
- `useLogout` hook — tidak disentuh
- Schema/types — tidak berubah
