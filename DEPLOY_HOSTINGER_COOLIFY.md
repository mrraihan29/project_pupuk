# Panduan Deploy Langkah-Demi-Langkah (VPS Hostinger + Coolify + Domain web.id + PostgreSQL)

Panduan ini dibuat supaya pengguna awam dapat mengikuti. Ikuti urutan langkah, jangan lompat.

## A. Prasyarat
- VPS Hostinger (Ubuntu/Debian) sudah berjalan.
- Coolify sudah terpasang di VPS dan bisa diakses via browser.
- Domain `pupuk.sie.web.id` dikelola di Hostinger.
- Anda memiliki akun GitHub (untuk menarik repo) atau sudah punya kode di VPS.

## B. Atur DNS
1) Masuk ke panel domain Hostinger.
2) Buat A record:
	- Host: `pupuk`
	- Value: IP publik VPS
	- TTL: default
3) Simpan. Tunggu propagasi (biasanya < 1 jam, seringnya menit).

## C. Siapkan Database PostgreSQL di Coolify
1) Di dashboard Coolify, buat **New Service** → pilih **PostgreSQL**.
2) Beri nama mis. `postgres-pupuk` → deploy.
3) Setelah aktif, buka detail service, catat:
	- HOST
	- PORT
	- DB (nama default, mis. `app` atau sesuai pilihan)
	- USER
	- PASSWORD
	Pastikan service punya volume (Coolify biasanya otomatis menambahkan) agar data tidak hilang.

## D. Siapkan Aplikasi di Coolify
1) Buat **New Application**.
2) Source: pilih Git repository `mrraihan29/project_pupuk` (branch `main`). Jika repo privat, set token/SSH key di Coolify.
3) Build type: Dockerfile (gunakan Dockerfile di root repo, sudah siap).
4) Port: 8000 (sesuai EXPOSE di Dockerfile). Coolify akan mem-proxy ke port publik.
5) Volumes (disarankan): tambahkan volume untuk folder `media/` supaya upload tersimpan:
	- Container path: `/app/media`
	- Volume: buat baru, mis. `media-pupuk`

## E. Isi Environment Variables (wajib)
Di tab Environment aplikasi Coolify, isi berikut (ganti dengan nilai asli):
```
SECRET_KEY=isi_kunci_acak_panjang
DEBUG=False
ALLOWED_HOSTS=pupuk.sie.web.id,127.0.0.1

DB_NAME=nama_db        # dari service Postgres
DB_USER=user_db        # dari service Postgres
DB_PASSWORD=pass_db    # dari service Postgres
DB_HOST=host_db        # dari service Postgres
DB_PORT=5432

CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_SAMESITE=Lax

# Opsional Gunicorn
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
```
Catatan: SECRET_KEY harus unik dan panjang. Jangan biarkan kosong.

## F. Deploy Aplikasi
1) Klik Deploy. Coolify akan build image dengan Dockerfile dan menjalankan container.
2) Entrypoint container otomatis melakukan:
	- `python manage.py migrate --noinput`
	- `python manage.py collectstatic --noinput`
	- Menjalankan gunicorn di port 8000.
3) Tunggu status Running.

## G. Aktifkan HTTPS/SSL
1) Di aplikasi Coolify, buka domain/HTTP settings.
2) Tambahkan domain `pupuk.sie.web.id`.
3) Aktifkan Let’s Encrypt SSL (pilih HTTP→HTTPS redirect).
4) Simpan dan re-deploy proxy jika diminta. Pastikan DNS sudah mengarah ke VPS agar sertifikat berhasil.

## H. Buat Superuser dan Login
1) Buka Console/Exec di aplikasi (Coolify menyediakan tombol Exec) atau jalankan:
	- `docker exec -it <nama_container> sh`
2) Jalankan: `python manage.py createsuperuser`
3) Isi username/password. User ini otomatis `is_staff` jika Anda set di admin.
4) Buka `https://pupuk.sie.web.id/` → login dengan superuser.

## I. Isi Data Wajib
1) Master Data Pupuk: pastikan harga beli/jual > 0 (per ton). Laporan akan menolak jika nol.
2) Jika perlu, isi Company Profile, Armada, Kios, dll.

## J. Smoke Test (cek cepat laporan)
1) Buat 1 Distribution (tanggal dalam bulan berjalan) untuk NPK/UREA.
2) Buat 1 Invoice (issue_date dalam rentang yang sama).
3) Buat 1 Biaya Operasional dengan status SELESAI dalam rentang.
4) Buka Laporan Keuangan, set filter tanggal sesuai. Pastikan angka omzet/HPP/opex berubah.

## K. Backup & Persistensi
- Postgres service Coolify sudah pakai volume (cek di service). Pastikan tidak dihapus.
- Volume `media/` sudah ditambahkan di langkah D.5.

## L. Troubleshooting Umum
- Laporan tidak berubah: cek filter tanggal, harga master > 0, ada distribusi/invoice di rentang, biaya status SELESAI, payment APPROVED jika ingin cash estimate.
- Akses ditolak ke master/laporan: pastikan user `is_staff`.
- Statis/ikon hilang: pastikan collectstatic sukses (ENTRYPOINT sudah menjalankannya) dan proxy tidak memblokir `/static/`.
- SSL gagal: cek DNS sudah mengarah ke VPS sebelum minta sertifikat Let’s Encrypt.

## M. Ringkas Alur
DNS → Buat Postgres service → Buat Application dengan Dockerfile → Set env → Tambah volume media → Deploy → Aktifkan SSL → Buat superuser → Isi master harga → Smoke test.
