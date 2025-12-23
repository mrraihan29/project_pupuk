import uuid
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum

# Mengambil Model dari Core yang baru saja kita sepakati
from core.models import JenisPupuk, Kecamatan, Kios, Armada, KiosAllocation

# ==========================================
# 1. SALES ORDER (PENEBUSAN / STOK VIRTUAL)
# ==========================================
class SalesOrder(models.Model):
    """
    Induk Transaksi Penebusan (Purchase Order ke Pabrik).
    Mewakili 'Stok Virtual' (Barang milik kita tapi masih di gudang pabrik).
    
    Logika:
    Stok Virtual akan berkurang jika:
    1. Ditarik ke Gudang Sendiri (WarehouseTransfer)
    2. Didistribusikan Langsung ke Kios (Distribution tipe VIRTUAL)
    """
    so_number = models.CharField("Nomor SO", max_length=50, unique=True, help_text="Nomor Sales Order dari Pabrik")
    date = models.DateField("Tanggal Penebusan")
    
    # User memilih manual jenis pupuk (Sesuai request: hapus auto-detect)
    jenis_pupuk = models.ForeignKey(JenisPupuk, on_delete=models.PROTECT, verbose_name="Jenis Pupuk")
    
    file_upload = models.FileField("Bukti DO/SO", upload_to='documents/so/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Penanda jika stok SO ini sudah habis total (0)
    is_closed = models.BooleanField("Selesai?", default=False, help_text="Centang otomatis jika sisa stok virtual habis")

    def __str__(self):
        return f"{self.so_number} - {self.jenis_pupuk.name}"

    class Meta:
        verbose_name = "Data Penebusan (SO)"
        verbose_name_plural = "Data Penebusan (SO)"
        ordering = ['-date']

    @property
    def total_tonnage(self):
        """Menghitung Total Tonase dari Alokasi Kecamatan"""
        return self.allocations.aggregate(total=Sum('tonnage'))['total'] or Decimal('0')

    def get_virtual_balance(self):
        """
        Menghitung Sisa Stok Virtual Real-time.
        Rumus: Total SO - (Total Transfer ke Gudang + Total Distribusi Langsung)
        """
        # 1. Hitung total yang sudah ditarik ke gudang fisik (Fisik In)
        transferred = self.transfers.aggregate(total=Sum('tonnage'))['total'] or Decimal('0')
        
        # 2. Hitung total yang didistribusikan LANGSUNG dari Pabrik (Virtual Out)
        distributed = self.distributions.filter(source_type='VIRTUAL').aggregate(total=Sum('tonnage'))['total'] or Decimal('0')
        
        return self.total_tonnage - transferred - distributed

    def save(self, *args, **kwargs):
        # Auto Close jika balance 0 (Logic sederhana)
        # Note: Idealnya ini dijalankan via Signal agar lebih reaktif
        super().save(*args, **kwargs)


class SalesOrderAllocation(models.Model):
    """
    Detail Alokasi per Kecamatan untuk 1 Nomor SO.
    (Parent-Child Relationship)
    """
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="allocations")
    kecamatan = models.ForeignKey(Kecamatan, on_delete=models.PROTECT, verbose_name="Alokasi Kecamatan")
    tonnage = models.DecimalField("Jumlah (Ton)", max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.kecamatan.name}: {self.tonnage} Ton"
    
    class Meta:
        verbose_name = "Rincian Alokasi SO"
        verbose_name_plural = "Rincian Alokasi SO"


# ==========================================
# 2. WAREHOUSE TRANSFER (TARIK KE GUDANG)
# ==========================================
class WarehouseTransfer(models.Model):
    """
    Transaksi memindahkan stok dari 'Virtual' (SO) ke 'Fisik' (Gudang Penyangga).
    Mengurangi Virtual Balance SO -> Menambah Physical Stock di Gudang.
    """
    source_so = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, verbose_name="Sumber SO", related_name="transfers")
    date = models.DateField("Tanggal Masuk Gudang", default=timezone.now)
    
    tonnage = models.DecimalField("Jumlah Ditarik (Ton)", max_digits=10, decimal_places=2)
    reference_code = models.CharField("No. Surat Jalan Pabrik", max_length=50, blank=True, help_text="Nomor referensi pengiriman dari pabrik ke gudang kita")
    
    notes = models.TextField("Catatan", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tarik {self.tonnage} Ton dari {self.source_so.so_number}"

    class Meta:
        verbose_name = "Stok Masuk Gudang (Fisik)"
        verbose_name_plural = "Stok Masuk Gudang (Fisik)"

    def clean(self):
        """
        VALIDASI PENTING:
        Tidak boleh menarik barang melebihi sisa stok virtual di SO tersebut.
        """
        if not self.source_so_id:
            return # Skip validation if SO not selected yet

        # Ambil sisa saldo virtual SAAT INI
        remaining = self.source_so.get_virtual_balance()
        
        # Jika sedang edit data lama, kita harus kembalikan nilai tonnage lama dulu ke saldo
        if self.pk:
            old_record = WarehouseTransfer.objects.get(pk=self.pk)
            remaining += old_record.tonnage
            
        if self.tonnage > remaining:
            raise ValidationError(f"Gagal! Sisa stok virtual SO {self.source_so.so_number} hanya tinggal {remaining:,.2f} Ton. Anda meminta {self.tonnage:,.2f} Ton.")


# ==========================================
# 3. DISTRIBUTION (SURAT JALAN)
# ==========================================
class Distribution(models.Model):
    """
    Transaksi Pengiriman ke Kios (Surat Jalan).
    Mendukung 'Hybrid Source':
    1. VIRTUAL: Barang dari Pabrik langsung ke Kios (Drop-off).
    2. PHYSICAL: Barang dari Gudang Penyangga dikirim ke Kios.
    """
    SOURCE_CHOICES = [
        ('VIRTUAL', 'Langsung dari Pabrik (Potong SO)'),
        ('PHYSICAL', 'Dari Gudang Penyangga (Potong Stok Fisik)'),
    ]

    # Identitas Surat Jalan
    no_surat_jalan = models.CharField("No. Surat Jalan", max_length=50, unique=True, editable=False)
    date = models.DateField("Tanggal Kirim")
    pkp_date = models.DateField("Tanggal PKP", help_text="Tanggal administrasi perpajakan/laporan")
    
    # Tujuan & Armada
    kios = models.ForeignKey(Kios, on_delete=models.PROTECT, verbose_name="Kios Tujuan")
    armada = models.ForeignKey(Armada, on_delete=models.PROTECT, verbose_name="Armada Pengirim")
    
    # Logika Stok
    source_type = models.CharField("Sumber Stok", max_length=10, choices=SOURCE_CHOICES, default='VIRTUAL')
    
    # Jika Virtual -> Wajib pilih SO mana yang dipotong
    source_so = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Ambil dari SO", related_name="distributions")
    
    # Jenis Pupuk:
    # - Jika VIRTUAL: Otomatis ikut SO.
    # - Jika PHYSICAL: User wajib pilih manual.
    jenis_pupuk = models.ForeignKey(JenisPupuk, on_delete=models.PROTECT, verbose_name="Jenis Pupuk")
    
    tonnage = models.DecimalField("Jumlah Kirim (Ton)", max_digits=10, decimal_places=2)
    
    # Snapshot Data Armada (Agar history aman jika Master Armada berubah/dihapus)
    driver_name_snapshot = models.CharField("Nama Supir (Saat Kirim)", max_length=100, blank=True)
    nopol_snapshot = models.CharField("Nopol (Saat Kirim)", max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 1. Generate Auto Number (Format: SJ/YYYYMMDD/XXXX)
        if not self.no_surat_jalan:
            today_str = timezone.now().strftime('%Y%m%d')
            uid = str(uuid.uuid4())[:4].upper()
            self.no_surat_jalan = f"SJ/{today_str}/{uid}"

        # 2. Snapshot Data Armada
        if self.armada:
            self.driver_name_snapshot = self.armada.driver_name
            self.nopol_snapshot = self.armada.plate_number

        # 3. Auto-Fill Jenis Pupuk jika dari SO (Virtual)
        if self.source_type == 'VIRTUAL' and self.source_so:
            self.jenis_pupuk = self.source_so.jenis_pupuk

        super().save(*args, **kwargs)

    def clean(self):
        # Validasi 1: Konsistensi Sumber Stok
        if self.source_type == 'VIRTUAL' and not self.source_so:
            raise ValidationError({'source_so': "Jika sumber stok adalah 'Langsung Pabrik', Anda WAJIB memilih Nomor SO!"})
        
        # Validasi 2: Cek Kecukupan Stok Virtual
        if self.source_type == 'VIRTUAL' and self.source_so:
            remaining = self.source_so.get_virtual_balance()
            
            # Handle Edit Logic
            if self.pk:
                old_record = Distribution.objects.get(pk=self.pk)
                # Kembalikan stok lama ke perhitungan
                if old_record.source_type == 'VIRTUAL' and old_record.source_so == self.source_so:
                    remaining += old_record.tonnage

            if self.tonnage > remaining:
                raise ValidationError({'tonnage': f"Stok Virtual SO {self.source_so.so_number} tidak cukup! Sisa: {remaining:,.2f} Ton."})
        
        # Validasi 3: Cek Kecukupan Stok Fisik
        if self.source_type == 'PHYSICAL':
            # Logic Cek Stok Fisik (Agak berat query-nya, kita gunakan helper function dari StockCard nanti)
            # Untuk sekarang kita skip validasi fisik di level Model clean() agar tidak circular import atau query berat.
            # Validasi fisik sebaiknya dilakukan di Form/View.
            agg = StockCard.objects.filter(jenis_pupuk=self.jenis_pupuk, stock_type='PHYSICAL').aggregate(
                total_in=Sum('qty_in'),
                total_out=Sum('qty_out'),
            )
            physical_remaining = (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))

            if self.pk:
                old_record = Distribution.objects.get(pk=self.pk)
                if old_record.source_type == 'PHYSICAL' and old_record.jenis_pupuk_id == self.jenis_pupuk_id:
                    physical_remaining += old_record.tonnage

            if self.tonnage and self.tonnage > physical_remaining:
                raise ValidationError({'tonnage': f"Stok fisik tidak cukup. Sisa {physical_remaining:,.2f} Ton untuk {self.jenis_pupuk.code}."})

        # Validasi 4: Cek kuota kios (alokasi tahunan)
        alloc = KiosAllocation.objects.filter(
            kios=self.kios,
            jenis_pupuk=self.jenis_pupuk,
            year=self.date.year
        ).first()

        if not alloc:
            raise ValidationError({'kios': f"Belum ada alokasi {self.jenis_pupuk.code} untuk tahun {self.date.year} di kios ini."})

        remaining_quota = alloc.quota_remaining

        # Jika edit dan alokasi tidak berubah, kembalikan tonase lama ke sisa saat validasi
        if self.pk:
            old = Distribution.objects.get(pk=self.pk)
            if (
                old.kios_id == self.kios_id and
                old.jenis_pupuk_id == self.jenis_pupuk_id and
                old.date.year == self.date.year
            ):
                remaining_quota += old.tonnage

        if self.tonnage and self.tonnage > remaining_quota:
            raise ValidationError({'tonnage': f"Kuota tersisa {remaining_quota:,.2f} Ton untuk {self.jenis_pupuk.code} tahun {self.date.year}."})

    def __str__(self):
        return f"{self.no_surat_jalan} - {self.kios.name}"

    class Meta:
        verbose_name = "Distribusi / Surat Jalan"
        verbose_name_plural = "Distribusi / Surat Jalan"
        ordering = ['-date', '-created_at']


# ==========================================
# 4. KARTU STOK (THE LEDGER)
# ==========================================
class StockCard(models.Model):
    """
    Buku Besar Stok (Ledger).
    Mencatat SETIAP pergerakan barang (Masuk/Keluar).
    Ini adalah 'Single Source of Truth' untuk saldo stok Fisik maupun Virtual.
    
    Catatan:
    Data di sini diisi otomatis via SIGNALS (gudang/signals.py).
    JANGAN input manual ke tabel ini kecuali untuk 'Stock Opname'.
    """
    STOCK_TYPE_CHOICES = [
        ('VIRTUAL', 'Stok Virtual (SO)'),
        ('PHYSICAL', 'Stok Fisik (Gudang)'),
    ]
    
    TRANSACTION_TYPES = [
        ('IN_SO', 'Penebusan Baru (Virtual In)'),
        ('OUT_TRF', 'Ditarik ke Gudang (Virtual Out)'),
        ('IN_TRF', 'Masuk Gudang (Physical In)'),
        ('OUT_DIST_V', 'Distribusi Langsung (Virtual Out)'),
        ('OUT_DIST_P', 'Distribusi Gudang (Physical Out)'),
        ('ADJUST', 'Penyesuaian / Opname'),
    ]

    date = models.DateField("Tanggal Transaksi")
    created_at = models.DateTimeField(auto_now_add=True)
    
    jenis_pupuk = models.ForeignKey(JenisPupuk, on_delete=models.CASCADE)
    stock_type = models.CharField("Tipe Stok", max_length=10, choices=STOCK_TYPE_CHOICES)
    transaction_type = models.CharField("Jenis Transaksi", max_length=20, choices=TRANSACTION_TYPES)
    
    # Referensi Dokumen (Disimpan sebagai string agar fleksibel menerima No SO / No SJ)
    reference_number = models.CharField("No. Ref (SO/SJ)", max_length=100)
    description = models.CharField("Keterangan", max_length=255)
    
    # Mutasi
    qty_in = models.DecimalField("Masuk", max_digits=12, decimal_places=2, default=0)
    qty_out = models.DecimalField("Keluar", max_digits=12, decimal_places=2, default=0)
    
    # Saldo Berjalan (Running Balance)
    # Diisi otomatis saat save() berdasarkan saldo sebelumnya
    balance = models.DecimalField("Saldo Akhir", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Kartu Stok (Ledger)"
        verbose_name_plural = "Kartu Stok (Ledger)"
        ordering = ['date', 'created_at']

    def __str__(self):
        return f"{self.date} - {self.jenis_pupuk.name} ({self.transaction_type})"