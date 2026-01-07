from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
# Import Armada untuk relasi Kartu Kontrol
from core.models import Armada, Kabupaten 
from decimal import Decimal

# ==========================================
# 1. BIAYA OPERASIONAL (PENGELUARAN)
# ==========================================
class BiayaOperasional(models.Model):
    KATEGORI_CHOICES = [
        ('ARMADA', 'Biaya Armada (Bensin, Servis, Tol)'),
        ('KANTOR', 'Biaya Kantor (Listrik, ATK, Gaji)'),
        ('LAINNYA', 'Biaya Lain-lain'),
    ]
    
    STATUS_CHOICES = [
        ('PROSES', 'Menunggu Approval Owner'),
        ('SELESAI', 'Disetujui / Selesai'),
        ('TOLAK', 'Ditolak'),
    ]

    tanggal = models.DateField(default=timezone.now)
    kategori_utama = models.CharField("Kategori", max_length=20, choices=KATEGORI_CHOICES)
    
    # RESTORASI FITUR: Relasi ke Armada (Nullable, karena biaya kantor tidak butuh mobil)
    armada = models.ForeignKey(Armada, on_delete=models.SET_NULL, null=True, blank=True, related_name='ops_list', verbose_name="Pilih Armada (Jika ada)")

    kabupaten = models.ForeignKey(Kabupaten, on_delete=models.PROTECT, null=True, blank=True, related_name='ops_list')
    
    deskripsi = models.TextField("Keterangan Detail", max_length=255)
    nominal = models.DecimalField("Jumlah (Rp)", max_digits=15, decimal_places=2)
    bukti_foto = models.ImageField(upload_to='keuangan/bukti/', null=True, blank=True)
    
    # RESTORASI FITUR: Status Approval
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PROSES')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        label = f"{self.get_kategori_utama_display()}"
        if self.armada:
            label += f" ({self.armada.plate_number})"
        return f"{label} - Rp {self.nominal:,.0f}"

    class Meta:
        verbose_name_plural = "Biaya Operasional"
        ordering = ['-tanggal', '-created_at']

# ==========================================
# 2. INVOICE (TIDAK ADA PERUBAHAN)
# ==========================================
class Invoice(models.Model):
    STATUS_CHOICES = [
        ('UNPAID', 'Belum Lunas'),
        ('PARTIAL', 'Cicilan Sebagian'),
        ('PAID', 'Lunas'),
    ]

    distribution = models.OneToOneField('gudang.Distribution', on_delete=models.CASCADE, related_name='invoice')
    inv_number = models.CharField("No. Invoice", max_length=50, unique=True, editable=False)
    issue_date = models.DateField("Tanggal Terbit")
    due_date = models.DateField("Jatuh Tempo")
    total_amount = models.DecimalField("Total Tagihan", max_digits=15, decimal_places=2)
    total_paid = models.DecimalField("Sudah Dibayar", max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UNPAID')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.inv_number} - {self.distribution.kios.name}"

    @property
    def remaining_balance(self):
        # Pastikan tidak ada None agar operasi aman
        total = self.total_amount or Decimal('0')
        paid = self.total_paid or Decimal('0')
        return total - paid

    def update_status(self):
        if self.total_paid >= self.total_amount:
            self.status = 'PAID'
        elif self.total_paid > 0:
            self.status = 'PARTIAL'
        else:
            self.status = 'UNPAID'
        self.save()

# ==========================================
# 3. PAYMENT (TIDAK ADA PERUBAHAN)
# ==========================================
class Payment(models.Model):
    STATUS_CHOICES = [
        ('APPROVED', 'Disetujui'),
        ('PENDING', 'Menunggu'),
        ('VOID', 'Void / Batal'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField("Tanggal Bayar", default=timezone.now)
    amount = models.DecimalField("Jumlah Bayar", max_digits=15, decimal_places=2)
    method = models.CharField("Metode", max_length=50, default="Transfer Bank")
    proof = models.ImageField("Bukti Transfer", upload_to='keuangan/payment/', null=True, blank=True)
    notes = models.TextField("Catatan", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='APPROVED')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pay {self.invoice.inv_number}"

    def clean(self):
        # SAFEGUARD: Cek apakah invoice sudah terhubung
        # Menghindari error RelatedObjectDoesNotExist saat form validation awal
        try:
            self.invoice
        except Invoice.DoesNotExist: 
            # Jika belum ada invoice (misal input manual di shell), skip validasi saldo
            return

        # Validasi: Tidak boleh bayar melebihi sisa tagihan
        sisa = self.invoice.remaining_balance or Decimal('0')

        if self.pk:
            old_amount = Payment.objects.get(pk=self.pk).amount or Decimal('0')
            sisa += old_amount
            
        amount = self.amount or Decimal('0')
        if amount > sisa:
            raise ValidationError(f"Kelebihan bayar! Sisa tagihan hanya Rp {sisa:,.0f}")