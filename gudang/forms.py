from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
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
        armada_qs = Armada.objects.filter(is_active=True)
        kios_qs = Kios.objects.filter(is_active=True)
        # Edit mode: include current armada/kios even if inactive
        if self.instance and self.instance.pk:
            if self.instance.armada_id:
                armada_qs = armada_qs | Armada.objects.filter(pk=self.instance.armada_id)
            if self.instance.kios_id:
                kios_qs = kios_qs | Kios.objects.filter(pk=self.instance.kios_id)
        self.fields['armada'].queryset = armada_qs.distinct()
        self.fields['kios'].queryset = kios_qs.distinct()


class DistributionItemForm(forms.ModelForm):
    class Meta:
        model = DistributionItem
        fields = ['jenis_pupuk', 'source_type', 'source_so', 'order_item', 'tonnage']
        widgets = {
            'jenis_pupuk': forms.Select(attrs={'class': 'form-select item-jenis'}),
            'source_type': forms.Select(attrs={'class': 'form-select item-source-type'}),
            'source_so': forms.Select(attrs={'class': 'form-select item-source-so'}),
            'order_item': forms.Select(attrs={'class': 'form-select item-order-item'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control item-tonnage', 'placeholder': 'Ton', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.kios_value = kwargs.pop('kios', None)
        super().__init__(*args, **kwargs)
        self.fields['jenis_pupuk'].queryset = JenisPupuk.objects.filter(is_active=True).order_by('name')
        self.fields['source_so'].queryset = SalesOrder.objects.filter(is_closed=False)
        self.fields['order_item'].queryset = OrderNoteItem.objects.filter(order__is_deleted=False, order__status=OrderNote.STATUS_OPEN)
        # Filter order_item by kios jika tersedia
        if self.kios_value:
            self.fields['order_item'].queryset = self.fields['order_item'].queryset.filter(order__kios_id=self.kios_value)

    def clean(self):
        data = super().clean()
        stype = data.get('source_type')
        so = data.get('source_so')
        ton = data.get('tonnage')
        order_item = data.get('order_item')
        jenis = data.get('jenis_pupuk')
        if stype == 'VIRTUAL' and not so:
            self.add_error('source_so', 'Pilih SO jika sumber stok Pabrik.')
        if stype == 'VIRTUAL' and so and jenis and so.jenis_pupuk_id != jenis.id:
            self.add_error('jenis_pupuk', f'Jenis pupuk harus {so.jenis_pupuk.name} (sesuai SO {so.so_number}).')
        # PHYSICAL: source_so opsional (boleh diisi sebagai referensi tanpa mempengaruhi saldo virtual SO)
        if stype == 'PHYSICAL' and so and jenis and so.jenis_pupuk_id != jenis.id:
            self.add_error('jenis_pupuk', f'Jenis pupuk harus {so.jenis_pupuk.name} (sesuai SO {so.so_number}).')
        if ton is not None and ton <= 0:
            self.add_error('tonnage', 'Tonase harus lebih dari 0')
        if order_item:
            if self.kios_value:
                try:
                    kios_id = int(self.kios_value)
                except (ValueError, TypeError):
                    kios_id = None
                if kios_id and order_item.order.kios_id != kios_id:
                    self.add_error('order_item', 'Pesanan tidak sesuai kios yang dipilih.')
            if jenis and order_item.jenis_pupuk_id != jenis.id:
                self.add_error('order_item', 'Pesanan berbeda jenis pupuk.')
            remaining = order_item.remaining_tonnage
            # EDIT FIX: saat edit item yang sudah ada, tonase lama item ini
            # terhitung dalam "delivered" (remaining=0). Kembalikan agar
            # validasi memperhitungkan bahwa item ini sendiri akan di-update.
            if self.instance.pk and self.instance.order_item_id == order_item.id:
                remaining += (self.instance.tonnage or 0)
            if ton and ton > remaining:
                self.add_error('tonnage', f'Tonase melebihi sisa pesanan ({remaining} Ton).')
        return data


class _DistributionItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, kios=None, **kwargs):
        self.kios = kios
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['kios'] = self.kios
        return kwargs


DistributionItemFormSet = inlineformset_factory(
    Distribution,
    DistributionItem,
    form=DistributionItemForm,
    formset=_DistributionItemFormSet,
    fields=('jenis_pupuk', 'source_type', 'source_so', 'order_item', 'tonnage'),
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
        so_qs = SalesOrder.objects.filter(is_closed=False)
        # Edit mode: include current SO even if closed
        if self.instance and self.instance.pk and self.instance.source_so_id:
            so_qs = so_qs | SalesOrder.objects.filter(pk=self.instance.source_so_id)
        self.fields['source_so'].queryset = so_qs.distinct()

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
        # Guard: tidak boleh kurangi tonase di bawah jumlah yang sudah dikirim
        if self.instance and self.instance.pk and ton is not None:
            delivered = self.instance.delivered_tonnage
            if ton < delivered:
                raise ValidationError(
                    f'Tonase tidak boleh kurang dari {delivered:,.2f} Ton '
                    f'(sudah terkirim via distribusi).'
                )
        return ton

    def clean(self):
        cleaned = super().clean()
        # Guard: peringatan jika menghapus item yang sudah punya pengiriman
        if cleaned.get('DELETE') and self.instance and self.instance.pk:
            delivered = self.instance.delivered_tonnage
            if delivered > 0:
                raise ValidationError(
                    f'Tidak bisa menghapus item yang sudah memiliki pengiriman '
                    f'({delivered:,.2f} Ton terkirim). Ubah tonase saja.'
                )
        return cleaned


OrderNoteItemFormSet = inlineformset_factory(
    OrderNote,
    OrderNoteItem,
    form=OrderNoteItemForm,
    fields=('jenis_pupuk', 'tonnage'),
    extra=1,
    can_delete=True,
)