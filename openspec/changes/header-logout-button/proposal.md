## Why

`UserMenu` di `ConsoleTopbar` saat ini menggunakan mode `collapsed` yang menampilkan inisial avatar, tapi dropdown-nya muncul ke arah bawah-kiri dan tidak terarah dari avatar. User mengalami kebingungan karena posisi dropdown tidak intuitif untuk konteks topbar kanan atas.

## What Changes

- Modifikasi `UserMenu` di `ConsoleTopbar` agar dropdown muncul ke bawah-kanan (dari avatar), bukan ke atas-kiri
- Topbar menggunakan `collapsed={true}` tapi posisi dropdown perlu disesuaikan untuk konteks kanan atas header
- Tidak ada perubahan pada `UserMenu` di sidebar (tetap pakai mode normal dengan dropdown ke atas)

## Capabilities

### New Capabilities
- `header-logout`: Dropdown logout yang muncul dari avatar di kanan atas topbar dengan posisi yang benar (bottom → top untuk sidebar, top → bottom untuk topbar)

### Modified Capabilities
- (tidak ada perubahan requirement level)

## Impact

- `apps/web/components/user-menu/user-menu.tsx` — tambah prop posisi atau variant untuk topbar context
- `apps/web/components/console-topbar/console-topbar.tsx` — pass prop baru ke `UserMenu`
