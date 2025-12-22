from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from datetime import date

# Import Models
from .models import SalesOrder, SalesOrderAllocation, Distribution, WarehouseTransfer, StockCard
from core.models import JenisPupuk, Kios, Armada

# ==========================================
# 1. FORM PENEBUSAN (SO) + ALOKASI
# ==========================================
class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ['so_number', 'date', 'jenis_pupuk', 'file_upload']
        widgets = {
            'so_number': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Contoh: 3101-A'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'jenis_pupuk': forms.Select(attrs={'class': 'form-select'}),
            'file_upload': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_so_number(self):
        # Validasi: Ubah input jadi huruf besar semua agar rapi
        return self.cleaned_data['so_number'].upper()

# Formset untuk Alokasi Kecamatan (Parent-Child)
AllocationFormSet = inlineformset_factory(
    SalesOrder, SalesOrderAllocation,
    fields=('kecamatan', 'tonnage'),
    extra=1, # Default tampil 1 baris kosong
    can_delete=True,
    widgets={
        'kecamatan': forms.Select(attrs={'class': 'form-select'}),
        'tonnage': forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ton', 
            'min': '0'
        }),
    }
)

# ==========================================
# 2. FORM DISTRIBUSI (SURAT JALAN)
# ==========================================
class DistributionForm(forms.ModelForm):
    class Meta:
        model = Distribution
        fields = ['date', 'pkp_date', 'kios', 'armada', 'source_type', 'source_so', 'jenis_pupuk', 'tonnage']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pkp_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kios': forms.Select(attrs={'class': 'form-select'}),
            'armada': forms.Select(attrs={'class': 'form-select'}),
            
            # ID Khusus untuk JavaScript (Smart Dropdown)
            'source_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_source_type'}),
            'source_so': forms.Select(attrs={'class': 'form-select', 'id': 'id_source_so'}),
            'jenis_pupuk': forms.Select(attrs={'class': 'form-select', 'id': 'id_jenis_pupuk'}),
            
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FILTER PENTING: Jangan tampilkan Armada yang sudah non-aktif (rusak/dijual)
        self.fields['armada'].queryset = Armada.objects.filter(is_active=True)
        # Jangan tampilkan Kios yang tutup permanen
        self.fields['kios'].queryset = Kios.objects.filter(is_active=True)

# ==========================================
# 3. FORM TRANSFER GUDANG (TARIK STOK)
# ==========================================
class WarehouseTransferForm(forms.ModelForm):
    class Meta:
        model = WarehouseTransfer
        fields = ['date', 'source_so', 'tonnage', 'reference_code', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            # Hanya tampilkan SO yang belum closed (Masih ada stok)
            'source_so': forms.Select(attrs={'class': 'form-select'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Jumlah Ditarik'}),
            'reference_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'No. Surat Jalan Pabrik'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hanya tampilkan SO yang belum ditutup (masih ada sisa)
        self.fields['source_so'].queryset = SalesOrder.objects.filter(is_closed=False)

# ==========================================
# 4. FORM STOCK OPNAME (MANUAL)
# ==========================================
class StockOpnameForm(forms.Form):
    """Form manual untuk menyesuaikan stok jika selisih"""
    date = forms.DateField(
        label="Tanggal Opname",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        initial=date.today
    )
    jenis_pupuk = forms.ModelChoiceField(
        queryset=JenisPupuk.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    stock_type = forms.ChoiceField(
        choices=StockCard.STOCK_TYPE_CHOICES,
        label="Lokasi Stok",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    actual_qty = forms.DecimalField(
        label="Stok Fisik Real (Ton)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    notes = forms.CharField(
        label="Catatan / Alasan Selisih",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        required=False
    )