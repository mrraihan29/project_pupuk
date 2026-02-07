# Roadmap Pengembangan SIM-DP

> Dokumen ini berisi seluruh rekomendasi pengembangan sistem berdasarkan audit menyeluruh terhadap fitur, business process, UX, keamanan, dan laporan. Disusun berdasarkan prioritas dampak bisnis dan efisiensi operasional.

---

## Status Saat Ini (Per 7 Februari 2026)

### Fitur yang Sudah Berjalan

| Modul | Fitur | Status |
|-------|-------|--------|
| **Dashboard** | KPI piutang, stok virtual/fisik, tagihan jatuh tempo, SO terlama | ✅ Aktif |
| **Catatan Order** | Buat pesanan masuk dari kios, multi-item | ✅ Aktif |
| **Penebusan (SO)** | Input SO + alokasi per kecamatan, auto stock card virtual | ✅ Aktif |
| **Transfer Gudang** | Tarik stok virtual → fisik, validasi saldo | ✅ Aktif |
| **Distribusi** | Surat jalan multi-item, source virtual/fisik, auto invoice | ✅ Aktif |
| **Kartu Stok** | Ledger virtual & fisik, export PDF bulanan | ✅ Aktif |
| **Stock Opname** | Penyesuaian stok manual | ✅ Aktif |
| **Tagihan & Pembayaran** | Invoice otomatis, pembayaran parsial/lunas | ✅ Aktif |
| **Biaya Operasional** | Input biaya + approval workflow (Owner) | ✅ Aktif |
| **Kartu Kontrol Armada** | Riwayat servis per kendaraan | ✅ Aktif |
| **Laporan Keuangan** | Laba rugi + aset, export CSV | ✅ Aktif |
| **Raport Kios** | Alokasi vs realisasi per kios | ✅ Aktif |
| **Master Data** | Kios, Armada, Pupuk & Harga, Kabupaten, Kecamatan | ✅ Aktif |
| **Pengaturan** | Profil Perusahaan, Manajemen User | ✅ Aktif |
| **Proteksi Stok** | Validasi stok tidak bisa minus, DB constraint, race condition guard | ✅ Aktif |

---

## Fase 1 — Fondasi (Prioritas Tertinggi)

> Memperbaiki masalah fundamental yang menghambat operasional harian.

### 1.1 Edit & Hapus Transaksi

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F1-01 | **Edit Sales Order** | Ubah alokasi kecamatan, tanggal, jenis pupuk. Signal otomatis update stock card | Medium |
| F1-02 | **Hapus Sales Order** | Soft delete dengan validasi: tidak bisa hapus jika sudah ada transfer/distribusi terkait | Medium |
| F1-03 | **Edit Distribusi / Surat Jalan** | Ubah item, tonase, kios tujuan. Auto-recalculate stock card, invoice, dan kuota | High |
| F1-04 | **Hapus / Batalkan Distribusi** | Restore stok & kuota, void invoice terkait | Medium |
| F1-05 | **Edit Transfer Gudang** | Ubah tonase yang ditarik ke gudang | Low |
| F1-06 | **Hapus Transfer Gudang** | Restore virtual balance, hapus stock card fisik | Low |
| F1-07 | **Edit Catatan Order** | Ubah item yang sudah dibuat (sebelum di-complete) | Low |

### 1.2 Pagination & Pencarian

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F1-08 | **Pagination di semua halaman list** | 25 record per halaman, navigasi halaman | Medium |
| F1-09 | **Filter tanggal (date range)** | Filter dari-sampai di setiap list transaksi | Medium |
| F1-10 | **Pencarian teks** | Cari berdasarkan nomor SO, nomor surat jalan, nama kios, dll | Medium |
| F1-11 | **Filter status** | Filter invoice (Lunas/Belum), SO (Open/Closed), Order (Terbuka/Selesai) | Low |

### 1.3 Tampilkan Data yang Sudah Ada Tapi Tersembunyi

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F1-12 | **Tampilkan bukti foto biaya operasional** | Di halaman list & approval, Owner bisa lihat bukti sebelum approve | Low |
| F1-13 | **Tampilkan bukti pembayaran** | Di halaman invoice, tampilkan foto/file bukti transfer | Low |
| F1-14 | **Tampilkan file SO (Bukti DO)** | Link download di halaman list SO | Low |
| F1-15 | **Tampilkan foto armada** | Thumbnail di halaman list armada | Low |

### 1.4 Perbaikan Role & Permission

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F1-16 | **Bedakan fungsi Admin vs Staff** | Tentukan aksi mana yang hanya boleh Admin, mana yang Staff juga bisa | Medium |
| F1-17 | **Proteksi aksi sensitif** | Hapus data, ubah harga, approve biaya → hanya role tertentu | Medium |
| F1-18 | **Kabupaten scope enforcement di create** | Pastikan user tidak bisa create transaksi di luar kabupaten aksesnya | Low |

---

## Fase 2 — Efisiensi Operasional

> Mengurangi waktu kerja harian pekerja dan mempercepat pengambilan keputusan.

### 2.1 Workflow & Shortcut

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F2-01 | **Tombol "Buat Surat Jalan" dari Catatan Order** | 1-klik dari list order → form distribusi sudah ter-prefill data kios & item | Low |
| F2-02 | **Quick action buttons di Dashboard** | Shortcut: "Buat SO Baru", "Buat Surat Jalan", "Catat Pembayaran" | Low |
| F2-03 | **Kabupaten filter sticky (tersimpan di session)** | Superuser tidak perlu pilih ulang kabupaten setiap pindah halaman | Medium |
| F2-04 | **Konfirmasi dialog untuk aksi kritis** | "Yakin hapus?" sebelum delete, "Yakin approve?" sebelum approve biaya | Low |
| F2-05 | **Tab Open/Closed di list SO** | Pisahkan SO aktif vs SO sudah habis untuk navigasi lebih cepat | Low |

### 2.2 Dashboard Alert & Notifikasi

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F2-06 | **Alert pesanan belum diproses** | Badge jumlah order note yang masih OPEN di dashboard | Low |
| F2-07 | **Alert biaya menunggu approval** | Khusus Owner: jumlah biaya operasional PENDING | Low |
| F2-08 | **Alert stok menipis** | Warning jika stok fisik jenis pupuk tertentu di bawah threshold | Medium |
| F2-09 | **Distribusi hari ini** | Jumlah surat jalan diterbitkan hari ini | Low |
| F2-10 | **Sistem notifikasi in-app** | Ganti bell icon dekoratif dengan notifikasi nyata (biaya baru, tagihan jatuh tempo) | High |

### 2.3 Laporan Umur Piutang (Aging Report)

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F2-11 | **Aging Report 30/60/90/120 hari** | Tabel kios vs bucket umur piutang, total per bucket | Medium |
| F2-12 | **Highlight kios penunggak** | Warna merah untuk piutang > 90 hari | Low |
| F2-13 | **Export aging report ke Excel/PDF** | Untuk meeting penagihan | Medium |

### 2.4 Credit Limit & Kontrol Piutang

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F2-14 | **Set credit limit per kios** | Field batas maksimal piutang di master kios | Low |
| F2-15 | **Blokir distribusi jika over limit** | Validasi saat buat surat jalan: total piutang kios + tagihan baru ≤ credit limit | Medium |
| F2-16 | **Warning di form distribusi** | Tampilkan sisa kredit kios di form sebelum submit | Low |

---

## Fase 3 — Profesionalisasi

> Meningkatkan kualitas dokumen, laporan, dan kelengkapan business process.

### 3.1 Export & Print Profesional

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F3-01 | **PDF Surat Jalan** | Generate PDF server-side, bisa kirim via WhatsApp/email | Medium |
| F3-02 | **PDF Invoice** | Sama, format profesional dengan logo perusahaan | Medium |
| F3-03 | **Export Raport Kios ke Excel** | Spreadsheet alokasi vs realisasi per kios | Medium |
| F3-04 | **Export distribusi per periode** | Rekap distribusi per kecamatan/kabupaten (Excel/PDF) untuk pelaporan dinas | Medium |
| F3-05 | **Statement of Account per kios** | Riwayat lengkap invoice & pembayaran per kios (PDF) | High |
| F3-06 | **Kwitansi pembayaran** | Bukti terima pembayaran yang bisa di-print | Low |
| F3-07 | **Bulk print surat jalan** | Cetak beberapa surat jalan sekaligus dalam 1 PDF | Medium |

### 3.2 Proses Bisnis Tambahan

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F3-08 | **Konfirmasi penerimaan barang** | Kios tanda tangan digital / checklist bahwa barang sudah diterima | High |
| F3-09 | **Proses retur barang** | Catat pengembalian dari kios → restore stok fisik + kuota + adjust invoice | High |
| F3-10 | **Void pembayaran** | Kemampuan membatalkan pembayaran yang salah catat (dengan approval Owner) | Medium |
| F3-11 | **Kategori biaya fleksibel** | Tambah/edit kategori biaya operasional tanpa ubah kode (simpan di database) | Medium |
| F3-12 | **Terms pembayaran per kios** | Set jatuh tempo berbeda per kios (7/14/30 hari) — sekarang hardcode 7 hari semua | Low |

### 3.3 Laporan Lanjutan

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F3-13 | **Laporan distribusi per periode** | Total distribusi per bulan/kecamatan/kabupaten dengan tren | Medium |
| F3-14 | **Ranking kios by revenue** | Kios paling aktif vs paling sedikit order | Low |
| F3-15 | **Utilisasi armada** | Kendaraan mana yang paling sering dipakai, idle berapa lama | Medium |
| F3-16 | **SO vs Realisasi per kecamatan** | Perbandingan alokasi SO vs distribusi aktual | Medium |
| F3-17 | **Tren bulanan (grafik)** | Chart penjualan, distribusi, dan revenue per bulan | Medium |
| F3-18 | **Laporan arus kas** | Inflow (pembayaran masuk) vs outflow (biaya keluar) per periode | Medium |
| F3-19 | **Riwayat harga pupuk** | Catat setiap perubahan harga (sekarang hanya simpan harga terkini) | Low |

---

## Fase 4 — Enhancement (Nice-to-Have)

> Peningkatan pengalaman pengguna dan otomasi lanjutan.

### 4.1 UX Improvement

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F4-01 | **Fix label "Owner / Admin" di topbar** | Tampilkan role sebenarnya dari user yang login | Low |
| F4-02 | **Loading indicator untuk aksi AJAX** | Spinner saat memuat data (contoh: riwayat armada) | Low |
| F4-03 | **Sidebar auto-expand active section** | Section yang berisi halaman aktif otomatis terbuka | Low |
| F4-04 | **Dark mode** | Opsi tampilan gelap untuk kenyamanan mata | Medium |
| F4-05 | **Responsive table improvement** | Tabel besar bisa di-scroll horizontal dengan header tetap | Low |

### 4.2 Otomasi & Integrasi

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F4-06 | **Notifikasi WhatsApp** | Kirim reminder tagihan jatuh tempo otomatis ke kios | High |
| F4-07 | **Email notifikasi** | Rangkuman harian untuk Owner: piutang, distribusi, biaya pending | Medium |
| F4-08 | **Audit trail / activity log** | Catat siapa melakukan apa dan kapan (create/edit/delete) | Medium |
| F4-09 | **Batch distribusi per armada** | 1 armada bawa barang ke beberapa kios → 1 trip, banyak surat jalan | Medium |
| F4-10 | **API endpoint untuk integrasi** | REST API untuk integrasi dengan sistem lain (accounting, ERP) | High |

### 4.3 Infrastruktur

| ID | Item | Detail | Effort |
|----|------|--------|--------|
| F4-11 | **Automated backup database** | Backup harian PostgreSQL ke cloud storage | Medium |
| F4-12 | **Rate limiting pada login** | Cegah brute force attack | Low |
| F4-13 | **Monitoring & error tracking** | Integrasi Sentry atau logging terpusat | Medium |
| F4-14 | **Perbaiki format No. Surat Jalan** | Sekarang pakai UUID 4 karakter (risiko collision) → ganti ke sequential number | Low |
| F4-15 | **Fix default tahun alokasi** | `KiosAllocation.year` default di-evaluate saat server start, tidak update saat tahun berganti | Low |

---

## Ringkasan Effort & Dampak

| Fase | Total Item | Estimasi Effort | Dampak |
|------|-----------|-----------------|--------|
| **Fase 1 — Fondasi** | 18 item | 2-3 minggu | 🔴 Kritis — memperbaiki masalah dasar yang menghambat kerja |
| **Fase 2 — Efisiensi** | 16 item | 2-3 minggu | 🟡 Tinggi — menghemat waktu kerja harian signifikan |
| **Fase 3 — Profesional** | 19 item | 3-4 minggu | 🟢 Sedang — meningkatkan kualitas output & kelengkapan proses |
| **Fase 4 — Enhancement** | 15 item | 3-4 minggu | 🔵 Bonus — UX premium & otomasi lanjutan |

> **Total: 68 item pengembangan**

---

## Catatan Teknis

- **Stack**: Django 5.0, Python 3.11, PostgreSQL, Bootstrap 5.3
- **Deploy**: Hostinger VPS via Coolify (Docker), auto-deploy dari GitHub
- **Test Suite**: 11 unit test aktif, 99/99 E2E simulation passed
- **Proteksi Stok**: DB constraint `quota_remaining >= 0`, `select_for_update` pada validasi, safety net di signal layer

---

*Dokumen ini dibuat pada 7 Februari 2026 dan akan di-update seiring perkembangan proyek.*
