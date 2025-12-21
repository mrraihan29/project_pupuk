from django import forms
from django.db.models import Sum
from core.models import KiosAllocation
from .models import Distribution, SalesOrder, StockAdjustment

# --- FORM PENEBUSAN (STOK MASUK) ---
class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        # SESUAI IMAGE 2: Kode SO -> Tgl Ngisi -> Kecamatan -> Tonase
        fields = ['so_code', 'entry_date', 'district', 'tonnage_initial']
        widgets = {
            'so_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '3101-xxxx (NPK) atau 3820-xxxx (UREA)'}),
            'entry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'district': forms.Select(attrs={'class': 'form-select'}),
            'tonnage_initial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def clean_so_code(self):
        # Validasi Kode SO agar sesuai aturan Client
        code = self.cleaned_data.get('so_code')
        if not (code.startswith('3101') or code.startswith('3820')):
            raise forms.ValidationError("Kode SO harus diawali 3101 (NPK) atau 3820 (UREA)")
        return code

# --- FORM PENYALURAN (STOK KELUAR) ---
class DistributionForm(forms.ModelForm):
    class Meta:
        model = Distribution
        # SESUAI IMAGE 3: Kode SO -> Tgl Ngirim -> Tgl PKP -> Kios -> Tonase -> Armada
        fields = ['sales_order', 'transaction_date', 'pkp_date', 'kios', 'tonnage_sent', 'armada', 'notes']
        widgets = {
            'sales_order': forms.Select(attrs={'class': 'form-select', 'id': 'id_sales_order'}), # ID PENTING UTK JS AUTO-FILL
            'transaction_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'pkp_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), # Field Baru (Administrasi)
            'kios': forms.Select(attrs={'class': 'form-select'}),
            'tonnage_sent': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_tonnage_kirim', 'step': '0.01'}),
            'armada': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Catatan tambahan...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter: Hanya tampilkan SO yang belum closed (Stok > 0)
        self.fields['sales_order'].queryset = SalesOrder.objects.filter(is_closed=False, tonnage_current__gt=0)

    def clean(self):
        cleaned_data = super().clean()
        kios = cleaned_data.get('kios')
        sales_order = cleaned_data.get('sales_order')
        tonnage = cleaned_data.get('tonnage_sent')
        tgl_transaksi = cleaned_data.get('transaction_date')
        
        if not (kios and sales_order and tonnage and tgl_transaksi):
            return

        # 1. Validasi Stok SO (Stok Gudang Fisik)
        if tonnage > sales_order.tonnage_current:
            raise forms.ValidationError(f"Stok SO Tidak Cukup! Sisa di Gudang: {sales_order.tonnage_current} Ton")

        # 2. Validasi Kuota Kecamatan (TRAFFIC LIGHT LOGIC)
        # Kita hitung total sisa kuota SATU KECAMATAN untuk jenis pupuk ini
        jenis_pupuk = sales_order.fertilizer_type
        tahun = tgl_transaksi.year
        
        # Ambil sisa kuota kecamatan (Pool)
        total_district_quota = KiosAllocation.objects.filter(
            kios__district=kios.district, # Filter berdasarkan Kecamatan Kios Tujuan
            year=tahun,
            fertilizer_type=jenis_pupuk
        ).aggregate(Sum('quota_remaining'))['quota_remaining__sum'] or 0

        # Jika Tonase Kirim > Sisa Jatah Kecamatan -> STOP (MERAH)
        if tonnage > total_district_quota:
            raise forms.ValidationError(
                f"GAGAL SALUR (RED LIGHT): Kuota Kecamatan {kios.district} untuk {jenis_pupuk} sudah habis! "
                f"Sisa Kecamatan: {total_district_quota} Ton."
            )

# --- FORM STOCK OPNAME (ADJUSTMENT) ---
class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['sales_order', 'actual_stock', 'reason']
        widgets = {
            'sales_order': forms.Select(attrs={'class': 'form-select'}),
            'actual_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Masukkan angka hasil hitung fisik...'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Jelaskan kenapa stok berubah...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hanya tampilkan SO yang belum closed atau masih relevan
        self.fields['sales_order'].queryset = SalesOrder.objects.filter(is_closed=False)
        self.fields['sales_order'].label = "Pilih Batch / Kode SO"