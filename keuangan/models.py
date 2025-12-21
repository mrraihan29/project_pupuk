from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

# Kita ambil referensi dari modul lain
from gudang.models import Distribution
from core.models import Armada

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('UNPAID', 'Belum Lunas (Merah)'),
        ('PARTIAL', 'Cicilan (Kuning)'),
        ('PAID', 'Lunas (Hijau)'),
    ]

    # Relasi One-to-One: 1 Penyaluran = 1 Invoice
    distribution = models.OneToOneField(Distribution, on_delete=models.CASCADE, related_name='invoice')
    
    invoice_no = models.CharField("No Invoice", max_length=50, unique=True)
    total_amount = models.DecimalField("Total Tagihan (Rp)", max_digits=15, decimal_places=2)
    
    amount_paid = models.DecimalField("Sudah Dibayar (Rp)", max_digits=15, decimal_places=2, default=Decimal('0.00'))
    # Sisa hutang kita hitung otomatis (property) atau field db, field db lebih mudah untuk filter query
    remaining_balance = models.DecimalField("Sisa Hutang (Rp)", max_digits=15, decimal_places=2)
    
    status = models.CharField("Status Pembayaran", max_length=10, choices=STATUS_CHOICES, default='UNPAID')
    due_date = models.DateField("Jatuh Tempo") # H+3 dari tgl kirim
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Hitung Sisa Hutang Otomatis
        self.remaining_balance = self.total_amount - self.amount_paid
        
        # Tentukan Status Otomatis
        if self.remaining_balance <= 0:
            self.status = 'PAID'
            self.remaining_balance = 0 # Jaga-jaga biar gak minus
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        else:
            self.status = 'UNPAID'
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_no} - {self.status}"

class Payment(models.Model):
    """
    Tabel untuk mencatat riwayat cicilan.
    Satu Invoice bisa punya banyak Payment (Cicilan).
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField("Nominal Bayar (Rp)", max_digits=15, decimal_places=2)
    payment_date = models.DateField("Tanggal Bayar", default=timezone.now)
    proof_image = models.ImageField("Bukti Transfer", upload_to='payments/', blank=True, null=True)
    notes = models.TextField("Catatan", blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bayar {self.amount} - {self.invoice.invoice_no}"

# --- MODUL OPERASIONAL (ANTI-FRAUD) ---
class BiayaOperasional(models.Model):
    # OPSI KATEGORI UTAMA (Sesuai Image 1)
    MAIN_CATEGORY = [
        ('ARMADA', 'Biaya Armada'),
        ('KANTOR', 'Biaya Kantor'),
    ]
    
    # OPSI JENIS PENGELUARAN (Sesuai Image 1)
    SUB_CATEGORY = [
        # Untuk Armada
        ('PERBAIKAN', 'Perbaikan / Service'),
        ('ONGKOS', 'Ongkos Jalan / BBM'),
        # Untuk Kantor
        ('RUTIN', 'Rutin (Gaji/Listrik)'),
        ('DADAKAN', 'Dadakan (Sumbangan/Lainnya)'),
    ]

    # OPSI URGENSI (Sesuai Image 2 - Kartu Kontrol)
    URGENCY_LEVEL = [
        ('NORMAL', 'Normal'),
        ('URGENT', 'URGENT'),
    ]

    STATUS_CHOICES = [
        ('PROSES', 'Dalam Proses'),
        ('SELESAI', 'Selesai'),
    ]

    # --- FIELD DATA ---
    kategori_utama = models.CharField(max_length=10, choices=MAIN_CATEGORY, default='KANTOR')
    jenis_biaya = models.CharField("Jenis Biaya", max_length=20, choices=SUB_CATEGORY)
    
    # Link ke Armada (Opsional, hanya jika kategori = ARMADA)
    armada = models.ForeignKey(Armada, on_delete=models.SET_NULL, null=True, blank=True)
    
    tanggal = models.DateField("Tgl Laporan")
    nominal = models.DecimalField(max_digits=12, decimal_places=0)
    
    description = models.TextField("Deskripsi Masalah/Keterangan")
    
    # --- FITUR KARTU KONTROL (Image 2) ---
    urgensi = models.CharField(max_length=10, choices=URGENCY_LEVEL, default='NORMAL')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SELESAI')
    tanggal_selesai = models.DateField("Tgl Selesai", null=True, blank=True)
    
    # Bukti Nota / Foto Kerusakan
    bukti_foto = models.ImageField(upload_to='biaya_ops/', null=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-set Tanggal Selesai jika status SELESAI & tgl kosong
        if self.status == 'SELESAI' and not self.tanggal_selesai:
            self.tanggal_selesai = self.tanggal
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.jenis_biaya} - Rp {self.nominal}"