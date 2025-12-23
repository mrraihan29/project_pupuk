1. Bug besar / inkonsistensi penulisan besar
- Alokasi kios tidak pernah berkurang saat distribusi; sinyal hanya menulis kartu stok tanpa mengubah `quota_remaining`, sehingga quota tahunan dan realisasi bisa meleset dari ledger [core/models.py](core/models.py) [gudang/signals.py](gudang/signals.py) [gudang/models.py](gudang/models.py).
- Laporan keuangan memakai `get_or_create` dengan lookup `jenis_pupuk__name` pada FK dan harga default per kg/tidak konsisten per ton, berpotensi FieldError atau valuasi salah signifikan [core/views.py](core/views.py).
- Perhitungan piutang di invoice list meng-aggregate semua invoice (termasuk PAID) sehingga total piutang yang ditampilkan bisa berlebih [keuangan/views.py](keuangan/views.py).
- ALLOWED_HOSTS kosong saat DEBUG=False tanpa env menyebabkan 400 di produksi; SECRET_KEY fallback hardcoded berisiko keamanan [sim_dp/settings.py](sim_dp/settings.py).

2. Bug kecil / inkonsistensi penulisan kecil
- Field `balance` di Kartu Stok tidak pernah dihitung/diupdate; bisa menyesatkan bila dibaca langsung dari DB [gudang/models.py](gudang/models.py) [gudang/signals.py](gudang/signals.py).
- Distribusi sumber FISIK tidak memvalidasi kecukupan stok fisik (hanya virtual yang dicek); potensi stok negatif [gudang/forms.py](gudang/forms.py) [gudang/models.py](gudang/models.py).
- Penutupan SO (`is_closed`) tidak pernah di-set otomatis ketika virtual balance habis; daftar SO di form masih menampilkan SO habis [gudang/models.py](gudang/models.py).
- Komentar dan pesan campur huruf besar/kecil; beberapa fungsi memakai konstanta magic number/hardcode harga tanpa konfigurasi (mis. laporan_keuangan) [core/views.py](core/views.py).

3. Fitur yang kurang maksimal
- Fitur stock opname hanya placeholder; belum ada penyesuaian stok dan kartu stok untuk selisih [gudang/views.py](gudang/views.py).
- Tidak ada audit log/approval untuk distribusi atau perubahan harga pupuk; risiko perubahan tanpa jejak [gudang/views.py](gudang/views.py) [core/views.py](core/views.py).
- Dashboard dan raport kios memakai query terpisah tanpa caching/annotate; bisa berat saat data besar [core/views.py](core/views.py).
- Tidak ada proteksi level grup di banyak view (kecuali owner_required di beberapa aksi keuangan); akses kontrol belum konsisten [core/views.py](core/views.py) [keuangan/views.py](keuangan/views.py).
- UX: banyak styling inline di template (kios_list, distribution_form, so_form) dan ketergantungan CDN (Bootstrap, icons, font); tidak ada bundling/minifikasi atau fallback offline [templates/**/*.html](templates) [static/css/app.css](static/css/app.css).
- JS formset/DOM manipulation tanpa debounce/validasi input (so_form clone row, kios_form add row) berpotensi data duplikat atau angka non-numerik tersimpan [templates/gudang/so_form.html](templates/gudang/so_form.html) [templates/core/kios_form.html](templates/core/kios_form.html).

4. Penulisan kode yang tidak professional / bisa lebih efektif
- Banyak logika bisnis ditempatkan di view procedural; sebaiknya diekstrak ke service/helper untuk mengurangi duplikasi (mis. perhitungan realisasi distribusi yang muncul di beberapa view) [core/views.py](core/views.py) [gudang/views.py](gudang/views.py).
- Nilai default/hardcode (harga, teks) tersebar tanpa konfigurasi terpusat; sebaiknya gunakan settings atau model konfigurasi [core/views.py](core/views.py).
- Tidak ada serializer/DTO untuk response JSON; API kecil masih manual dict tanpa tipe/validasi [keuangan/views.py](keuangan/views.py).
- Penanganan formset di kios_update tidak menutup kemungkinan race/validasi ulang saat multiple users; perlu atomic + clean konsisten [core/views.py](core/views.py).
- CSS besar di app.css tanpa purge/minify dan banyak style inline di template; struktur BEM/utility tidak konsisten, menyulitkan reuse [static/css/app.css](static/css/app.css) [templates/**/*.html](templates).
- Tidak ada asset versioning/cache busting; bergantung CDN tanpa SRI/fallback dapat menimbulkan risiko integritas dan ketersediaan [templates/base.html](templates/base.html).

5. To do list perbaikan
[x] **Fundamental**: Kurangi quota kios saat distribusi (sinkron dengan ledger) dan cegah distribusi melebihi jatah tahunan per kios [core/models.py](core/models.py) [gudang/signals.py](gudang/signals.py).
[x] **Fundamental**: Perbaiki laporan_keuangan: gunakan FK langsung untuk harga pupuk, konsisten satuan (per ton), dan pisahkan konfigurasi harga agar tidak hardcode [core/views.py](core/views.py).
[x] **Fundamental**: Hitung piutang hanya dari invoice UNPAID/PARTIAL; sesuaikan query aggregate di invoice_list [keuangan/views.py](keuangan/views.py).
[x] **Konsistensi data**: Tambahkan validasi stok fisik pada distribusi FISIK dan auto-close SO saat virtual balance nol; sertakan update StockCard.balance atau hapus field jika tidak dipakai [gudang/forms.py](gudang/forms.py) [gudang/models.py](gudang/models.py) [gudang/signals.py](gudang/signals.py).
[x] **Konsistensi & keamanan**: Tambah SRI + crossorigin + fallback lokal untuk CDN (Bootstrap/Icons) dan ekstrak JS sidebar ke file statis; form opname sudah dihitungkan selisih ke Kartu Stok sebagai ADJUST. Rencana bundling/purge: paketkan vendor (bootstrap, icons, layout) via django-compressor/whitenoise collectstatic; purge CSS dengan django-compressor + purgecss (target templates/**/*.html) dan pindahkan inline JS/CSS tersisa ke static/js|css. Service layer & audit: next step susun modul services/stock.py & services/finance.py untuk distribusi/realisasi/harga + audit log model `AuditTrail` + status approval (draft/approved) pada Distribution dan Master Harga sebelum publish. [templates/base.html](templates/base.html) [static/css/app.css](static/css/app.css) [static/js/layout.js](static/js/layout.js) [gudang/views.py](gudang/views.py).
