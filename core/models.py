from django.db import models
from django.utils import timezone
from decimal import Decimal

# ==========================================
# 1. MASTER COMPANY PROFILE (Singleton)
# ==========================================
class CompanyProfile(models.Model):
    name = models.CharField("Nama Perusahaan", max_length=100, default="CV. BERKAH TANI")
    address = models.TextField("Alamat Kantor", default="Jl. Raya Salatiga - Semarang KM 5")
    phone = models.CharField("No. Telepon/WA", max_length=50, default="0812-3456-7890")
    email = models.EmailField("Email", max_length=100, blank=True)
    logo = models.ImageField("Logo Perusahaan", upload_to='company/', blank=True, null=True)
    
    # Info Bank untuk Footer Invoice
    bank_name = models.CharField("Nama Bank", max_length=50, blank=True)
    bank_account = models.CharField("No. Rekening", max_length=50, blank=True)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Profil Perusahaan"
        verbose_name_plural = "Profil Perusahaan"

# ==========================================
# 2. MASTER WILAYAH (KECAMATAN)
# ==========================================
class Kecamatan(models.Model):
    name = models.CharField("Nama Kecamatan", max_length=100, unique=True)
    code = models.CharField("Kode Wilayah", max_length=10, blank=True, null=True)
    
    # TAMBAHAN: Target Tahunan (Penting untuk Laporan Realisasi)
    target_tonnage = models.DecimalField("Target Tahunan (Ton)", max_digits=10, decimal_places=2, default=Decimal('0'))
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Master Kecamatan"
        ordering = ['name']

# ==========================================
# 3. MASTER JENIS PUPUK
# ==========================================
class JenisPupuk(models.Model):
    name = models.CharField("Nama Pupuk", max_length=50, unique=True) # NPK, UREA
    code = models.CharField("Kode Singkatan", max_length=10, unique=True) 
    
    # TAMBAHAN DARI SAYA: Warna untuk UI Dashboard
    color = models.CharField("Warna Label (Bootstrap/Hex)", max_length=20, default="primary", help_text="primary, success, danger, warning, atau kode Hex")
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name_plural = "Master Jenis Pupuk"

# ==========================================
# 4. MASTER DATA KIOS
# ==========================================
class Kios(models.Model):
    name = models.CharField("Nama Kios", max_length=100)
    pic_name = models.CharField("Nama Penanggung Jawab", max_length=100)
    
    # Relasi ke Kecamatan
    kecamatan = models.ForeignKey(Kecamatan, on_delete=models.PROTECT, related_name='kios_list', verbose_name="Kecamatan")
    
    address = models.TextField("Alamat Lengkap")
    phone = models.CharField("Nomor HP", max_length=20)
    is_active = models.BooleanField("Aktif?", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.kecamatan.name})"

    class Meta:
        verbose_name_plural = "Data Kios"

# ==========================================
# 5. ALLOCATION (KUOTA KIOS)
# ==========================================
class KiosAllocation(models.Model):
    """
    Menyimpan kuota pupuk per tahun per kios.
    Design ini excellent untuk scalability.
    """
    kios = models.ForeignKey(Kios, on_delete=models.CASCADE, related_name='allocations')
    year = models.IntegerField("Tahun Anggaran", default=timezone.now().year)
    jenis_pupuk = models.ForeignKey(JenisPupuk, on_delete=models.CASCADE, verbose_name="Jenis Pupuk")
    
    quota_original = models.DecimalField("Jatah Awal (Ton)", max_digits=10, decimal_places=2, default=Decimal('0'))
    quota_remaining = models.DecimalField("Sisa Kuota (Ton)", max_digits=10, decimal_places=2, default=Decimal('0'))

    @property
    def quota_used(self):
        # Derived usage to avoid storing duplicate state
        return self.quota_original - self.quota_remaining

    def __str__(self):
        return f"{self.kios.name} - {self.jenis_pupuk.code} {self.year}"

    class Meta:
        unique_together = ('kios', 'year', 'jenis_pupuk')
        verbose_name_plural = "Alokasi Kuota Kios"

# ==========================================
# 6. MASTER ARMADA
# ==========================================
class Armada(models.Model):
    plate_number = models.CharField("Plat Nomor", max_length=15, unique=True)
    vehicle_type = models.CharField("Jenis Kendaraan", max_length=50) # Engkel, Fuso
    driver_name = models.CharField("Nama Supir", max_length=100)
    photo_url = models.ImageField("Foto Kendaraan", upload_to='armada/', blank=True, null=True) # Saya ubah jadi ImageField agar lebih mudah
    is_active = models.BooleanField("Aktif?", default=True)

    def __str__(self):
        return f"{self.plate_number} - {self.driver_name}"

    class Meta:
        verbose_name_plural = "Data Armada"

# ==========================================
# 7. MASTER HARGA
# ==========================================
class FertilizerPrice(models.Model):
    jenis_pupuk = models.OneToOneField(JenisPupuk, on_delete=models.CASCADE, verbose_name="Jenis Pupuk", related_name='price_config')
    
    price_buy = models.DecimalField("Harga Tebus (Per KG)", max_digits=15, decimal_places=2)
    price_sell = models.DecimalField("Harga Jual (Per KG)", max_digits=15, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Harga {self.jenis_pupuk.code}"

    class Meta:
        verbose_name_plural = "Master Harga Pupuk"