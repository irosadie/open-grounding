## 1. UserMenu Component

- [x] 1.1 Tambah prop `dropdownPosition?: "top" | "bottom"` ke interface `UserMenuProps`
- [x] 1.2 Update collapsed mode dropdown: gunakan `top-full right-0 mt-2` saat `dropdownPosition="bottom"`
- [x] 1.3 Pastikan default `dropdownPosition="top"` tidak mengubah behavior existing sidebar

## 2. ConsoleTopbar

- [x] 2.1 Pass `dropdownPosition="bottom"` ke `<UserMenu collapsed />` di `ConsoleTopbar`

## 3. Verifikasi

- [x] 3.1 Typecheck pass (`bun run typecheck`)
- [x] 3.2 Dropdown muncul ke bawah-kanan dari avatar di topbar
- [x] 3.3 Dropdown sidebar tetap muncul ke atas (tidak berubah)
