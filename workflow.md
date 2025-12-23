# Cara Kerja SIM-DP

Panduan ini menjelaskan alur kerja harian tanpa istilah teknis. Ikuti berurutan supaya stok, tagihan, dan laporan keuangan konsisten.

---

## 1) Siapkan Data Utama
- Lengkapi profil perusahaan (nama, alamat, kontak, logo, rekening) agar kop surat rapi.
- Tambah master pupuk (mis. NPK, UREA) dan set harga beli & jual per ton.
- Tambah armada (nopol, sopir) untuk referensi pengiriman.
- Tambah kios dan isi jatah (alokasi) per tahun; sistem akan memotong alokasi otomatis saat distribusi.

## 2) Barang Masuk (Penebusan dari Pabrik)
- Catat penebusan/PO dari pabrik beserta tanggal dan tonase.
- Hasil: stok bertambah sebagai “stok virtual” (barang milik Anda, masih di pabrik/gudang asal).

## 3) Barang Keluar (Distribusi ke Kios)
- Buat Surat Jalan: pilih kios, tanggal kirim, armada, tonase, dan sumber stok (virtual dari pabrik atau fisik dari gudang sendiri).
- Stok berkurang sesuai sumber yang dipilih; alokasi kios ikut berkurang.
- Sistem otomatis membuat Invoice (tagihan) untuk kios tersebut.
- Cetak Surat Jalan untuk sopir.

## 4) Pembayaran Tagihan Kios
- Masuk ke daftar Invoice dan klik “Bayar”.
- Isi tanggal, metode, nominal, lampirkan bukti.
- Set status pembayaran:
	- **APPROVED** = diterima, masuk hitungan kas dan mengurangi sisa tagihan.
	- **PENDING** = menunggu konfirmasi, belum dihitung kas.
	- **VOID** = dibatalkan, tidak dihitung kas.
- Sistem menolak nominal di atas sisa tagihan (muncul pesan kesalahan jika berlebih).

## 5) Biaya Operasional
- Catat pengeluaran (armada/kantor/lainnya) beserta bukti.
- Status awal **PROSES** (belum disetujui): dianggap hutang sementara di neraca.
- Owner setujui menjadi **SELESAI** jika valid: biaya masuk ke laporan laba rugi dan mengurangi kas periode.

## 6) Laporan & Monitoring
- **Dashboard**: pantau piutang berjalan, stok virtual (di pabrik), stok fisik (di gudang), dan invoice jatuh tempo.
- **Laporan Keuangan** (Laba Rugi + Neraca singkat):
	- Omzet dari penjualan yang terbit invoice-nya.
	- HPP dari penebusan ke pabrik.
	- Biaya dari pengeluaran berstatus SELESAI.
	- Kas estimasi = pembayaran APPROVED periode − biaya SELESAI periode.
	- Liabilitas = total pengeluaran berstatus PROSES.
	- Ekuitas dihitung otomatis agar aset = liabilitas + ekuitas.
- **Kartu Stok**: audit pergerakan masuk/keluar dan saldo akhir per jenis pupuk.

## 7) Ringkas Alur End-to-End
Setup master → Penebusan dari pabrik → Buat Surat Jalan → Invoice otomatis → Terima pembayaran (set status) → Catat biaya → Owner approve biaya → Cek laporan.