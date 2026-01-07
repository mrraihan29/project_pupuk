# Cara Kerja SIM-DP

Panduan ini menjelaskan alur kerja harian tanpa istilah teknis. Ikuti berurutan supaya stok, tagihan, dan laporan keuangan konsisten.

---

## 1) Siapkan Data Utama
- Lengkapi profil perusahaan (nama, alamat, kontak, logo, rekening) agar kop surat rapi.
- Tambah master pupuk (mis. NPK, UREA) dan set harga beli & jual **per ton**; kedua nilai wajib diisi (>0) agar laporan keuangan dapat dibuka.
- Tambah armada (nopol, sopir) untuk referensi pengiriman.
- Tambah kios dan isi jatah (alokasi) per tahun; sistem akan memotong alokasi otomatis saat distribusi.

## 2) Catatan Order (Opsional, Sebelum Penebusan)
- Catat permintaan kios per kecamatan beserta daftar pupuk & tonase (multi-item per order).
- Gunakan sebagai acuan penyusunan penebusan/Surat Jalan; data ini **tidak** mengubah stok atau alokasi.
- Tandai selesai jika order terpenuhi; entri selesai disembunyikan dari daftar.

## 3) Barang Masuk (Penebusan dari Pabrik)
- Catat penebusan/PO dari pabrik beserta tanggal dan tonase.
- Hasil: stok bertambah sebagai “stok virtual” (barang milik Anda, masih di pabrik/gudang asal).

## 4) Barang Keluar (Distribusi ke Kios)
- Buat Surat Jalan: pilih kios, tanggal kirim, armada, tonase, dan sumber stok (virtual dari pabrik atau fisik dari gudang sendiri).
- Stok berkurang sesuai sumber yang dipilih; alokasi kios ikut berkurang.
- Sistem otomatis membuat Invoice (tagihan) untuk kios tersebut.
- Cetak Surat Jalan untuk sopir.

## 5) Pembayaran Tagihan Kios
- Masuk ke daftar Invoice dan klik “Bayar”.
- Isi tanggal, metode, nominal, lampirkan bukti.
- Set status pembayaran:
	- **APPROVED** = diterima, masuk hitungan kas dan mengurangi sisa tagihan.
	- **PENDING** = menunggu konfirmasi, belum dihitung kas.
	- **VOID** = dibatalkan, tidak dihitung kas.
- Sistem menolak nominal di atas sisa tagihan (muncul pesan kesalahan jika berlebih).

## 6) Biaya Operasional
- Catat pengeluaran (armada/kantor/lainnya) beserta bukti.
- Status awal **PROSES** (belum disetujui): dianggap hutang sementara di neraca.
- Owner setujui menjadi **SELESAI** jika valid: biaya masuk ke laporan laba rugi dan mengurangi kas periode.

## 7) Laporan & Monitoring
- **Dashboard**: pantau piutang berjalan, stok virtual (di pabrik), stok fisik (di gudang), dan invoice jatuh tempo.
- **Laporan Keuangan** (Laba Rugi + Neraca singkat):
	- Omzet dari penjualan yang terbit invoice-nya.
	- HPP dari penebusan ke pabrik.
	- Biaya dari pengeluaran berstatus SELESAI.
	- Kas estimasi = pembayaran APPROVED periode − biaya SELESAI periode.
	- Liabilitas = total pengeluaran berstatus PROSES.
	- Ekuitas dihitung otomatis agar aset = liabilitas + ekuitas.
	- Jika master harga pupuk belum lengkap atau ≤0, halaman ini meminta Anda melengkapi harga terlebih dahulu.
- **Kartu Stok**: audit pergerakan masuk/keluar dan saldo akhir per jenis pupuk.

## 8) Ringkas Alur End-to-End
Setup master → (Opsional) Catatan Order → Penebusan dari pabrik → Buat Surat Jalan → Invoice otomatis → Terima pembayaran (set status) → Catat biaya → Owner approve biaya → Cek laporan.