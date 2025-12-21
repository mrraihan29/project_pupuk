from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from core.models import Kios, Armada, KiosAllocation

# --- 1. SALES ORDER (SO) - INBOUND ---
class SalesOrder(models.Model):
    # Opsi Kecamatan (Sesuaikan dengan wilayah kerja Client)
    DISTRICT_CHOICES = [
        ('Bancak', 'Bancak'),
        ('Pabelan', 'Pabelan'),
        ('Suruh', 'Suruh'),
        ('Getasan', 'Getasan'),
        ('Tuntang', 'Tuntang'),
        # Tambahkan kecamatan lain sesuai Video 1
    ]

    so_code = models.CharField("Kode SO (Batch)", max_length=50, unique=True)
    fertilizer_type = models.CharField(max_length=10, choices=[('NPK', 'NPK'), ('UREA', 'UREA')])
    
    # REVISI IMAGE 2: Stok terikat Kecamatan
    district = models.CharField("Alokasi Kecamatan", max_length=50, choices=DISTRICT_CHOICES, default='Bancak') 
    
    tonnage_initial = models.DecimalField("Tonase Awal", max_digits=10, decimal_places=2)
    tonnage_current = models.DecimalField("Sisa Stok", max_digits=10, decimal_places=2)
    entry_date = models.DateField("Tanggal Ngisi")
    maturity_date = models.DateField("Jatuh Tempo Gudang", blank=True)
    is_closed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Auto-detect Type
        if self.so_code.startswith('3101'): self.fertilizer_type = 'NPK'
        elif self.so_code.startswith('3820'): self.fertilizer_type = 'UREA'
        
        # Auto-calc Jatuh Tempo (21 Hari)
        if not self.maturity_date:
            from datetime import timedelta
            self.maturity_date = self.entry_date + timedelta(days=21)
            
        # Set initial current
        if not self.pk:
            self.tonnage_current = self.tonnage_initial
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.so_code} ({self.district})"


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
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE)
    kios = models.ForeignKey(Kios, on_delete=models.CASCADE, related_name='distributions')
    armada = models.ForeignKey(Armada, on_delete=models.SET_NULL, null=True)
    
    tonnage_sent = models.DecimalField("Tonase Kirim", max_digits=10, decimal_places=2)
    transaction_date = models.DateField("Tanggal Ngirim (Fisik)")
    
    pkp_date = models.DateField("Tanggal PKP (Admin)", help_text="Tanggal yang tercetak di Surat Jalan & Invoice") 
    
    surat_jalan_no = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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

class StockAdjustment(models.Model):
    """
    Model untuk mencatat segala bentuk koreksi stok (Stock Opname).
    Menggunakan pendekatan 'Audit Log' dimana setiap perubahan tercatat history-nya.
    """
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='adjustments')
    
    # Snapshot data sebelum diedit (Untuk bukti audit)
    previous_stock = models.DecimalField("Stok Sistem (Sebelum)", max_digits=10, decimal_places=2, editable=False)
    
    # Inputan User (Fisik Nyata)
    actual_stock = models.DecimalField("Stok Fisik (Actual)", max_digits=10, decimal_places=2)
    
    # Hasil kalkulasi (Selisih)
    adjustment_qty = models.DecimalField("Selisih (Adjustment)", max_digits=10, decimal_places=2, editable=False)
    
    reason = models.TextField("Alasan Koreksi", help_text="Wajib diisi detail. Contoh: Stock Opname Bulan November 2025")
    executor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Eksekutor")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ATOMIC TRANSACTION: Pastikan semua proses db di bawah ini sukses bareng atau gagal bareng
        with transaction.atomic():
            # 1. Ambil Stok Lama dari Database (Real-time)
            # Kita refresh dari db untuk menghindari race condition
            self.sales_order.refresh_from_db()
            self.previous_stock = self.sales_order.tonnage_current
            
            # 2. Hitung Selisih
            # Rumus: Stok Fisik - Stok Sistem
            # Contoh: Fisik 90 - Sistem 100 = -10 (Kurang/Hilang)
            # Contoh: Fisik 110 - Sistem 100 = +10 (Kelebihan/Retur tak tercatat)
            self.adjustment_qty = self.actual_stock - self.previous_stock
            
            # 3. Update Master Stok (Sales Order)
            self.sales_order.tonnage_current = self.actual_stock
            self.sales_order.save()
            
            # 4. Simpan Record Adjustment Ini
            super().save(*args, **kwargs)
            
            # 5. Catat ke KARTU STOK (StockCard)
            # Ini wajib agar "Running Balance" di kartu stok tetap nyambung matematikanya.
            from .models import StockCard # Import di dalam untuk hindari circular import
            
            # Tentukan tipe transaksi berdasarkan plus/minus
            trx_type = 'IN' if self.adjustment_qty > 0 else 'OUT'
            ref_note = f"STOCK OPNAME #{self.pk} ({self.reason})"
            
            StockCard.objects.create(
                sales_order=self.sales_order,
                trx_type=trx_type,
                reference_number=ref_note,
                qty_change=abs(self.adjustment_qty), # Selalu positif di log
                balance_after=self.actual_stock
            )

    def __str__(self):
        return f"Adj #{self.pk} - {self.sales_order.so_code}"

    class Meta:
        verbose_name = "Stock Opname / Adjustment"
        ordering = ['-created_at']