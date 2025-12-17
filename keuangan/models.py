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
    
    amount_paid = models.DecimalField("Sudah Dibayar (Rp)", max_digits=15, decimal_places=2, default=0)
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
    KATEGORI_CHOICES = [
        ('BENSIN', 'Bahan Bakar (BBM)'),
        ('MAKAN', 'Uang Makan Supir'),
        ('TOL', 'Biaya Tol / Parkir'),
        ('SERVIS', 'Servis & Sparepart (Maintenance)'), # <-- Kritis untuk Fraud
        ('LAIN', 'Lain-lain'),
    ]

    armada = models.ForeignKey(Armada, on_delete=models.CASCADE, related_name='operational_costs')
    kategori = models.CharField(max_length=10, choices=KATEGORI_CHOICES)
    nominal = models.DecimalField("Biaya (Rp)", max_digits=12, decimal_places=2)
    
    tanggal = models.DateField(default=timezone.now)
    keterangan = models.TextField("Detail (Nama Bengkel/Ket)", blank=True)
    
    # Bukti Foto (Wajib untuk audit)
    foto_bukti = models.ImageField("Foto Nota/Struk", upload_to='operasional/', blank=True, null=True)
    
    # Status Approval Owner
    is_approved = models.BooleanField("Di-ACC Owner?", default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.armada.plate_number} - {self.kategori} - Rp {self.nominal}"

    class Meta:
        verbose_name_plural = "Biaya Operasional"