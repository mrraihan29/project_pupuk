# SIM-DP (Manajemen Distribusi Pupuk)

Aplikasi Django untuk mengelola master data pupuk, distribusi ke kios, penebusan (SO), stok fisik/virtual, invoicing, dan laporan laba rugi.

## Fitur Utama
- Master data: Jenis Pupuk (CRUD + harga per ton), Kios & alokasi, Armada, Kecamatan, Company Profile.
- Operasional gudang: Sales Order (penebusan/virtual), Warehouse Transfer (tarik stok ke fisik), Distribution (surat jalan ke kios).
- Keuangan: Invoice, Pembayaran, Biaya Operasional (dengan status), Laporan Laba Rugi (omzet & HPP basis distribusi/invoice), Neraca singkat.
- Keamanan dasar: akses master & laporan keuangan dibatasi `is_staff`, harga master wajib > 0.

## Persyaratan
- Python 3.11
- PostgreSQL
- Dependensi lihat `requirements.txt`

## Konfigurasi Environment (.env)
Contoh minimal:
```
SECRET_KEY=isi_kunci_acak_panjang
DEBUG=False
ALLOWED_HOSTS=pupuk.sie.web.id,127.0.0.1

DB_NAME=nama_db
DB_USER=user_db
DB_PASSWORD=pass_db
DB_HOST=host_db
DB_PORT=5432

CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_SAMESITE=Lax
```

## Setup Lokal (tanpa Docker)
```
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```
Akses: http://127.0.0.1:8000/ (login sebagai superuser/staff).

## Struktur Penting
- `core/` : master data, laporan keuangan, harga pupuk.
- `gudang/` : SO, warehouse transfer, distribusi.
- `keuangan/` : invoice, payment, biaya operasional.
- `templates/` : halaman utama, master data, laporan.
- `static/` : aset statis.

## Laporan Laba Rugi (logika ringkas)
- Omzet: prefer Invoice (issue_date dalam rentang); jika kosong pakai distribusi tonase × harga jual master.
- HPP: distribusi tonase × harga beli master (per ton).
- Opex: BiayaOperasional status SELESAI dalam rentang.
- Kas estimasi: pembayaran APPROVED dalam rentang dikurangi opex.
- Persediaan: saldo stok fisik (StockCard PHYSICAL) × harga beli master.

## Otorisasi
- Halaman master pupuk, jenis pupuk, dan laporan keuangan: hanya `user.is_staff`.
- Halaman setup (users, kecamatan, company profile): juga memeriksa staff.

## Catatan Harga
- Harga master disimpan per ton. Form menolak harga <= 0. Laporan akan blok jika harga nol/kosong.

## Docker (singkat)
```
docker build -t sim-dp .
docker run -e SECRET_KEY=... -e DEBUG=False -e ALLOWED_HOSTS=... -e DB_* ... -p 8000:8000 sim-dp
```
Entrypoint container: migrate -> collectstatic -> gunicorn.

## Troubleshooting cepat
- Laporan tidak berubah: pastikan filter tanggal mencakup transaksi, harga master > 0, ada distribusi/invoice dalam rentang, biaya status SELESAI, payment APPROVED.
- 403 akses master/keuangan: user harus `is_staff`.
- Statis tidak muncul di produksi: pastikan `collectstatic` jalan dan reverse proxy melayani `/static/`, `/media/`.
