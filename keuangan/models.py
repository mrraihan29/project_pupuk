from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

# ==========================================
# 1. BIAYA OPERASIONAL (PENGELUARAN)
# ==========================================
class BiayaOperasional(models.Model):
    """
    Mencatat semua pengeluaran perusahaan (Cash Out).
    """
    KATEGORI_CHOICES = [
        ('ARMADA', 'Biaya Armada (Bensin, Servis, Tol, Supir)'),
        ('KANTOR', 'Biaya Kantor (Listrik, WiFi, ATK, Gaji Admin)'),
        ('LAINNYA', 'Biaya Lain-lain (Sumbangan, Tak Terduga)'),
    ]

    tanggal = models.DateField(default=timezone.now)
    # Field baru menggunakan 'kategori_utama' agar lebih deskriptif
    kategori_utama = models.CharField("Kategori Pengeluaran", max_length=20, choices=KATEGORI_CHOICES)
    
    deskripsi = models.CharField("Keterangan Detail", max_length=255, help_text="Contoh: Bensin Truk H-1234-AB")
    nominal = models.DecimalField("Jumlah (Rp)", max_digits=15, decimal_places=2)
    bukti_foto = models.ImageField(upload_to='keuangan/bukti/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_kategori_utama_display()} - Rp {self.nominal:,.0f}"

    class Meta:
        verbose_name_plural = "Biaya Operasional"
        ordering = ['-tanggal']

# ==========================================
# 2. INVOICE / TAGIHAN (PENDAPATAN)
# ==========================================
class Invoice(models.Model):
    STATUS_CHOICES = [
        ('UNPAID', 'Belum Lunas'),
        ('PARTIAL', 'Cicilan Sebagian'),
        ('PAID', 'Lunas'),
    ]

    # Relasi ke Distribusi (One-to-One)
    distribution = models.OneToOneField('gudang.Distribution', on_delete=models.CASCADE, related_name='invoice')
    
    inv_number = models.CharField("No. Invoice", max_length=50, unique=True, editable=False)
    issue_date = models.DateField("Tanggal Terbit")
    due_date = models.DateField("Jatuh Tempo")
    
    total_amount = models.DecimalField("Total Tagihan (Rp)", max_digits=15, decimal_places=2)
    total_paid = models.DecimalField("Sudah Dibayar (Rp)", max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UNPAID')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.inv_number} - {self.distribution.kios.name}"

    @property
    def remaining_balance(self):
        return self.total_amount - self.total_paid

    def update_status(self):
        """Update status otomatis berdasarkan pembayaran"""
        if self.total_paid >= self.total_amount:
            self.status = 'PAID'
        elif self.total_paid > 0:
            self.status = 'PARTIAL'
        else:
            self.status = 'UNPAID'
        self.save()

# ==========================================
# 3. PEMBAYARAN (PAYMENT)
# ==========================================
class Payment(models.Model):
    """
    Mencatat cicilan/pelunasan dari Kios.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    
    # Restorasi & Mapping nama field lama ke baru:
    # payment_date -> date
    date = models.DateField("Tanggal Bayar", default=timezone.now)
    
    amount = models.DecimalField("Jumlah Bayar (Rp)", max_digits=15, decimal_places=2)
    method = models.CharField("Metode", max_length=50, default="Transfer Bank")
    
    # proof_image -> proof
    proof = models.ImageField("Bukti Transfer", upload_to='keuangan/payment/', null=True, blank=True)
    
    # RESTORASI FITUR: Menambahkan kembali field notes yang sempat hilang
    notes = models.TextField("Catatan", blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pay {self.invoice.inv_number} - Rp {self.amount:,.0f}"

    def clean(self):
        # Validasi: Tidak boleh bayar melebihi sisa tagihan
        # Note: self.pk check diperlukan agar saat edit data tidak error sendiri
        sisa = self.invoice.remaining_balance
        if self.pk:
            old_amount = Payment.objects.get(pk=self.pk).amount
            sisa += old_amount
            
        if self.amount > sisa:
            raise ValidationError(f"Kelebihan bayar! Sisa tagihan hanya Rp {sisa:,.0f}")