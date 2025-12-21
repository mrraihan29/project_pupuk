from django.db import models
from django.utils import timezone
from decimal import Decimal
# --- 1. MASTER KIOS ---
class Kios(models.Model):
    name = models.CharField("Nama Kios", max_length=100)
    pic_name = models.CharField("Nama Penanggung Jawab", max_length=100)
    address = models.TextField("Alamat Lengkap")
    district = models.CharField("Kecamatan", max_length=50, help_text="Kecamatan sangat penting untuk fitur Fluid Allocation")
    phone = models.CharField("Nomor HP", max_length=20)
    is_active = models.BooleanField("Aktif?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.district})"

    class Meta:
        verbose_name_plural = "Data Kios"


class KiosAllocation(models.Model):
    """
    Menyimpan kuota pupuk per tahun agar history tahun lalu tidak hilang.
    """
    FERTILIZER_TYPES = [
        ('NPK', 'NPK (Merah)'),
        ('UREA', 'UREA (Biru)'),
    ]

    kios = models.ForeignKey(Kios, on_delete=models.CASCADE, related_name='allocations')
    year = models.IntegerField("Tahun Anggaran", default=timezone.now().year)
    fertilizer_type = models.CharField("Jenis Pupuk", max_length=10, choices=FERTILIZER_TYPES)
    
    # Kuota Awal (Jatah RDKK)
    quota_original = models.DecimalField("Jatah Awal (Ton)", max_digits=10, decimal_places=2, default=Decimal('0'))
    # Kuota Sisa (Berkurang saat transaksi)
    quota_remaining = models.DecimalField("Sisa Kuota (Ton)", max_digits=10, decimal_places=2, default=Decimal('0'))

    def __str__(self):
        return f"{self.kios.name} - {self.fertilizer_type} {self.year}"

    class Meta:
        unique_together = ('kios', 'year', 'fertilizer_type') # Satu kios hanya boleh punya 1 jatah NPK per tahun
        verbose_name_plural = "Alokasi Kuota Kios"


# --- 2. MASTER ARMADA ---
class Armada(models.Model):
    plate_number = models.CharField("Plat Nomor", max_length=15, unique=True)
    vehicle_type = models.CharField("Jenis Kendaraan", max_length=50, help_text="Contoh: Truk Engkel, Pickup L300")
    driver_name = models.CharField("Nama Supir", max_length=100)
    # Foto kita simpan sebagai URL text dulu agar tidak ribet setup media storage di awal
    photo_url = models.CharField("URL Foto Kendaraan", max_length=255, blank=True, null=True)
    is_active = models.BooleanField("Aktif?", default=True)

    def __str__(self):
        return f"{self.plate_number} - {self.driver_name}"

    class Meta:
        verbose_name_plural = "Data Armada"


# --- 3. MASTER HARGA ---
class FertilizerPrice(models.Model):
    FERTILIZER_TYPES = [
        ('NPK', 'NPK (Merah)'),
        ('UREA', 'UREA (Biru)'),
    ]

    fertilizer_type = models.CharField("Jenis Pupuk", max_length=10, choices=FERTILIZER_TYPES, unique=True)
    price_buy = models.DecimalField("Harga Tebus (Beli)", max_digits=15, decimal_places=2, help_text="Harga beli dari Holding")
    price_sell = models.DecimalField("Harga Jual (Distribusi)", max_digits=15, decimal_places=2, help_text="Harga jual ke Kios")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Harga {self.fertilizer_type}"

    class Meta:
        verbose_name_plural = "Master Harga Pupuk"
        
