from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal
from django.db import transaction

# Import models from core app
from core.models import Kios, Armada, KiosAllocation

# --- 1. SALES ORDER (SO) - INBOUND ---
class SalesOrder(models.Model):
    FERTILIZER_TYPES = [
        ('NPK', 'NPK (Merah)'),
        ('UREA', 'UREA (Biru)'),
    ]

    # URD Part G: Kode SO menentukan jenis pupuk
    so_code = models.CharField("Kode SO", max_length=50, unique=True, help_text="Awal 3101=NPK, 3820=UREA")
    fertilizer_type = models.CharField("Jenis Pupuk", max_length=10, choices=FERTILIZER_TYPES, editable=False) # Readonly karena auto-detect
    
    tonnage_initial = models.DecimalField("Tonase Awal", max_digits=10, decimal_places=2)
    tonnage_current = models.DecimalField("Sisa Stok", max_digits=10, decimal_places=2)
    
    entry_date = models.DateField("Tanggal Penebusan", default=timezone.now)
    # URD Part G: Jatuh Tempo Gudang (21 Hari)
    maturity_date = models.DateField("Jatuh Tempo Gudang", editable=False) # Readonly karena auto-calc
    
    is_closed = models.BooleanField("Sudah Habis?", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Validasi Manual (Safety Net)
        if self.so_code:
            prefix = self.so_code[:4]
            if prefix not in ['3101', '3820']:
                raise ValidationError("Kode SO tidak valid! Harus diawali 3101 (NPK) atau 3820 (UREA).")

    def save(self, *args, **kwargs):
        # 1. AUTO DETECT JENIS PUPUK (URD Part G Point 1)
        if self.so_code.startswith('3101'):
            self.fertilizer_type = 'NPK'
        elif self.so_code.startswith('3820'):
            self.fertilizer_type = 'UREA'
        
        # 2. AUTO SET STOK SAAT PERTAMA KALI DIBUAT
        if not self.pk: # Jika ini data baru
            self.tonnage_current = self.tonnage_initial
            
        # 3. AUTO CALC JATUH TEMPO (URD Part G Point 2)
        if self.entry_date:
            self.maturity_date = self.entry_date + timedelta(days=21)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.so_code} ({self.fertilizer_type}) - Sisa: {self.tonnage_current} Ton"

    class Meta:
        verbose_name_plural = "Data Penebusan (SO)"
        ordering = ['-entry_date'] # Yang terbaru muncul paling atas


# --- 2. KARTU STOK (LOG MUTASI) ---
class StockCard(models.Model):
    TRX_TYPES = [
        ('IN', 'Masuk (Penebusan)'),
        ('OUT', 'Keluar (Penyaluran)'),
    ]

    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='stock_cards')
    trx_type = models.CharField("Tipe Transaksi", max_length=5, choices=TRX_TYPES)
    reference_number = models.CharField("Referensi", max_length=100, help_text="No SO atau No Surat Jalan")
    
    qty_change = models.DecimalField("Mutasi (Ton)", max_digits=10, decimal_places=2)
    balance_after = models.DecimalField("Saldo Akhir (Ton)", max_digits=10, decimal_places=2)
    
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date.strftime('%d/%m/%Y')} - {self.sales_order.so_code} - {self.trx_type}"

    class Meta:
        verbose_name_plural = "Kartu Stok (Log)"
        ordering = ['-date']
        
# --- 3. DISTRIBUTION (PENYALURAN) - OUTBOUND ---
class Distribution(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name='distributions', verbose_name="Sumber SO")
    kios = models.ForeignKey(Kios, on_delete=models.PROTECT, related_name='distributions')
    armada = models.ForeignKey(Armada, on_delete=models.PROTECT, related_name='distributions')
    
    tonnage_sent = models.DecimalField("Tonase Dikirim", max_digits=10, decimal_places=2)
    transaction_date = models.DateField("Tanggal Kirim", default=timezone.now)
    
    # Nomor Surat Jalan kita generate otomatis nanti
    surat_jalan_no = models.CharField("No Surat Jalan", max_length=50, blank=True, unique=True)
    
    notes = models.TextField("Catatan", blank=True, help_text="Catatan khusus / Fluid Allocation")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # VALIDASI 1: Cek Stok Gudang (Anti-Minus)
        if self.tonnage_sent and self.sales_order:
            if self.tonnage_sent > self.sales_order.tonnage_current:
                raise ValidationError(f"Stok Tidak Cukup! Sisa SO ini hanya {self.sales_order.tonnage_current} Ton.")

        # VALIDASI 2: Cek Kesesuaian Jenis Pupuk SO vs Alokasi?
        # Nanti kita handle di UI agar Admin tidak salah pilih SO

    def save(self, *args, **kwargs):
        # ATOMIC TRANSACTION (Risk R-05 & NFR-01)
        # Memastikan semua update database di bawah ini sukses bareng atau gagal bareng
        with transaction.atomic():
            is_new = self.pk is None
            
            # 1. Generate Nomor Surat Jalan (Format: SJ/Tahun/Bulan/ID)
            if not self.surat_jalan_no:
                last_id = Distribution.objects.order_by('-id').first()
                new_id = (last_id.id + 1) if last_id else 1
                self.surat_jalan_no = f"SJ/{timezone.now().strftime('%Y%m')}/{new_id:04d}"

            # Simpan Data Distribusi Dulu
            super().save(*args, **kwargs)

            if is_new:
                # 2. Kurangi Stok SO
                self.sales_order.tonnage_current -= self.tonnage_sent
                if self.sales_order.tonnage_current == 0:
                    self.sales_order.is_closed = True
                self.sales_order.save()

                # 3. Potong Kuota Kios (Fluid Allocation Logic)
                # Cari alokasi yang cocok (Tahun sama, Jenis Pupuk sama)
                # Logic: SO Code 3101 -> NPK. SO Code 3820 -> UREA.
                jenis_pupuk = self.sales_order.fertilizer_type
                tahun_sekarang = self.transaction_date.year
                
                try:
                    allocation = KiosAllocation.objects.get(
                        kios=self.kios, 
                        year=tahun_sekarang, 
                        fertilizer_type=jenis_pupuk
                    )
                    allocation.quota_remaining -= self.tonnage_sent
                    allocation.save()
                except KiosAllocation.DoesNotExist:
                    # Jika data alokasi belum dibuat, biarkan dulu (atau raise Error tergantung kebijakan)
                    # Untuk sekarang kita pass, anggap admin lupa input master alokasi
                    pass

    def __str__(self):
        return f"{self.surat_jalan_no} - {self.kios.name} ({self.tonnage_sent} Ton)"

    class Meta:
        verbose_name_plural = "Data Penyaluran (Distribusi)"
        ordering = ['-transaction_date']