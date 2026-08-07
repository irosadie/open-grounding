# Spec: Header Logout

## Capability

Dropdown user menu yang muncul dari avatar di kanan atas topbar, dengan posisi dropdown yang benar (ke bawah) sesuai konteks header.

## Requirements

### REQ-1: Prop `dropdownPosition`
`UserMenu` harus menerima prop opsional `dropdownPosition?: "top" | "bottom"` dengan default `"top"`.

### REQ-2: Posisi dropdown collapsed mode
Ketika `collapsed={true}`:
- `dropdownPosition="top"` → dropdown muncul ke atas (`bottom-full`), centered horizontal (behavior existing)
- `dropdownPosition="bottom"` → dropdown muncul ke bawah (`top-full`), aligned ke kanan (`right-0`)

### REQ-3: Topbar menggunakan `dropdownPosition="bottom"`
`ConsoleTopbar` harus pass `dropdownPosition="bottom"` ke `UserMenu`.

### REQ-4: Sidebar tidak berubah
`UserMenu` di sidebar tetap tanpa prop `dropdownPosition` (default `"top"`), behavior tidak berubah.

### REQ-5: Isi dropdown tetap sama
Dropdown tetap menampilkan: nama user, email user, dan tombol Logout.

### REQ-6: Logout behavior tidak berubah
Klik Logout tetap memanggil `signOut({ redirect: false })` lalu `router.push("/login")`.

## Out of Scope

- Perubahan hook `useLogout`
- Perubahan schema atau types
- Animasi atau transisi tambahan
- Menu item tambahan selain Logout
