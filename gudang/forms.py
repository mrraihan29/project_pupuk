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
    # Set required=False agar tidak error saat hidden
    jenis_pupuk = forms.ModelChoiceField(
        queryset=JenisPupuk.objects.filter(is_active=True),
        required=False, 
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_jenis_pupuk'})
    )
    
    source_so = forms.ModelChoiceField(
        queryset=SalesOrder.objects.filter(is_closed=False),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_source_so'})
    )

    class Meta:
        model = Distribution
        fields = ['date', 'pkp_date', 'kios', 'armada', 'source_type', 'source_so', 'jenis_pupuk', 'tonnage']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pkp_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kios': forms.Select(attrs={'class': 'form-select'}),
            'armada': forms.Select(attrs={'class': 'form-select'}),
            'source_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_source_type'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['armada'].queryset = Armada.objects.filter(is_active=True)
        self.fields['kios'].queryset = Kios.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get('source_type')
        source_so = cleaned_data.get('source_so')
        jenis_pupuk = cleaned_data.get('jenis_pupuk')
        
        # LOGIC CERDAS:
        if source_type == 'VIRTUAL':
            # Jika ambil dari Pabrik, WAJIB pilih SO
            if not source_so:
                self.add_error('source_so', 'Wajib memilih Nomor SO untuk transaksi Pabrik.')
            else:
                # OTOMATIS ISI JENIS PUPUK DARI SO (Mengatasi Error "Nothing Happens")
                cleaned_data['jenis_pupuk'] = source_so.jenis_pupuk
                
        elif source_type == 'PHYSICAL':
            # Jika ambil dari Gudang, WAJIB pilih Jenis Pupuk manual
            if not jenis_pupuk:
                self.add_error('jenis_pupuk', 'Wajib memilih Jenis Pupuk untuk transaksi Gudang.')
        
        return cleaned_data
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