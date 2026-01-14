from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from datetime import date

# Import Models
from .models import SalesOrder, SalesOrderAllocation, Distribution, DistributionItem, WarehouseTransfer, StockCard, OrderNote, OrderNoteItem
from core.models import JenisPupuk, Kios, Armada, Kecamatan

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
        fields = ['date', 'pkp_date', 'kios', 'armada']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pkp_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kios': forms.Select(attrs={'class': 'form-select'}),
            'armada': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['armada'].queryset = Armada.objects.filter(is_active=True)
        self.fields['kios'].queryset = Kios.objects.filter(is_active=True)


class DistributionItemForm(forms.ModelForm):
    class Meta:
        model = DistributionItem
        fields = ['jenis_pupuk', 'source_type', 'source_so', 'tonnage']
        widgets = {
            'jenis_pupuk': forms.Select(attrs={'class': 'form-select item-jenis'}),
            'source_type': forms.Select(attrs={'class': 'form-select item-source-type'}),
            'source_so': forms.Select(attrs={'class': 'form-select item-source-so'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control item-tonnage', 'placeholder': 'Ton', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['jenis_pupuk'].queryset = JenisPupuk.objects.filter(is_active=True)
        self.fields['source_so'].queryset = SalesOrder.objects.filter(is_closed=False)

    def clean(self):
        data = super().clean()
        stype = data.get('source_type')
        so = data.get('source_so')
        ton = data.get('tonnage')
        if stype == 'VIRTUAL' and not so:
            self.add_error('source_so', 'Pilih SO jika sumber stok Pabrik.')
        if stype == 'PHYSICAL':
            data['source_so'] = None
        if ton is not None and ton <= 0:
            self.add_error('tonnage', 'Tonase harus lebih dari 0')
        return data


DistributionItemFormSet = inlineformset_factory(
    Distribution,
    DistributionItem,
    form=DistributionItemForm,
    fields=('jenis_pupuk', 'source_type', 'source_so', 'tonnage'),
    extra=1,
    can_delete=True,
)
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
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'})
    )
    notes = forms.CharField(
        label="Catatan / Alasan Selisih",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        required=False
    )


# ==========================================
# 5. FORM CATATAN ORDER
# ==========================================
class OrderNoteForm(forms.ModelForm):
    class Meta:
        model = OrderNote
        fields = ['date', 'kecamatan', 'kios', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kecamatan': forms.Select(attrs={'class': 'form-select', 'id': 'id_kecamatan'}),
            'kios': forms.Select(attrs={'class': 'form-select', 'id': 'id_kios'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catatan (opsional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kios'].queryset = Kios.objects.filter(is_active=True)
        self.fields['kecamatan'].queryset = Kecamatan.objects.all()

        kecamatan_id = None
        if self.is_bound:
            kecamatan_id = self.data.get('kecamatan')
        elif self.instance and self.instance.kecamatan_id:
            kecamatan_id = self.instance.kecamatan_id

        if kecamatan_id:
            self.fields['kios'].queryset = Kios.objects.filter(kecamatan_id=kecamatan_id, is_active=True)


class OrderNoteItemForm(forms.ModelForm):
    class Meta:
        model = OrderNoteItem
        fields = ['jenis_pupuk', 'tonnage']
        widgets = {
            'jenis_pupuk': forms.Select(attrs={'class': 'form-select'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton', 'step': '0.01', 'min': '0.01'}),
        }

    def clean_tonnage(self):
        ton = self.cleaned_data.get('tonnage')
        if ton is not None and ton <= 0:
            raise ValidationError('Tonase harus lebih dari 0')
        return ton


OrderNoteItemFormSet = inlineformset_factory(
    OrderNote,
    OrderNoteItem,
    form=OrderNoteItemForm,
    fields=('jenis_pupuk', 'tonnage'),
    extra=1,
    can_delete=True,
)