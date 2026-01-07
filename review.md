## To Do: Multi-Kabupaten Access Control (detailed)
	- Add model Kabupaten (name, code, is_active, timestamps); register in admin.
	- Add FK kabupaten to Kecamatan (required) with migration; adjust forms/list filters.
	- Add FK kabupaten (nullable) to User (or profile) with default NULL for superuser; enforce non-superuser must choose exactly one kabupaten.
	- Extend Setup pages: combine/neighbor Master Kabupaten + Master Kecamatan; superuser-only create/edit/delete; block delete if Kecamatan exists.
	- User management form: add kabupaten dropdown (required for staff/admin, optional for superuser); validation to prevent multiple kabupaten per user.
	- Implement helper/mixin `scope_by_kabupaten(user, qs, via)` to auto-filter by user.kabupaten when not superuser.
	- Apply to key views/queries: kios, allocations, SO, transfer, distribusi, order notes, invoice/payment, biaya operasional, laporan keuangan, dashboard stats, kartu stok.
	- Prefer joining via kios__kecamatan__kabupaten or kecamatan__kabupaten to avoid extra FK churn.
	- For superuser: add kabupaten filter dropdown on list/report pages (dashboard widgets, laporan keuangan, invoice list, distribusi list, SO list, order notes, biaya ops); default "Semua".
	- For admin kabupaten: hide/lock filter; always scoped.
	- Sidebar: add link to Master Kabupaten under Setup.
	- Create migrations for Kabupaten, FK on Kecamatan, FK on User; run with empty data (safe) but include forward/backward defaults.
	- Seed path: superuser creates kabupaten pertama, lalu kecamatan, lalu assign admin dengan kabupaten tersebut.
	- Add unit/behavior checks where pricing stays global (no kabupaten FK on harga pupuk).
## To Do: Multi-Kabupaten Access Control (detailed)
- [x] Data model: Kabupaten, FK Kecamatan->Kabupaten, UserProfile.kabupaten for non-superuser scoping; admin registration.
- [x] Setup/CRUD: Master Kabupaten page (create/edit/delete with guard if kecamatan exists); Kecamatan form lists kabupaten; sidebar link; user form enforces kabupaten for non-superuser.
- [x] Query scoping helper: `scope_by_kabupaten` + `get_scope_kabupaten` implemented and applied to kios, SO list, transfer list, distribusi list/create, order notes list/create, raport kios, dashboard lists, invoice list, biaya operasional list/create, laporan keuangan, kartu kontrol. StockCard remains global (no kabupaten field) pending design decision.
- [x] UI/UX filtering: superuser kabupaten dropdown on list/report pages (dashboard, laporan keuangan, invoice list, distribusi list, SO list, order notes, biaya ops); admin kabupaten locked/hidden.
- [x] Migration & safety: migrations exist/applied (core 0003, keuangan 0005); empty-data friendly. Seed flow: superuser create kabupaten, kecamatan, assign admin with kabupaten.

