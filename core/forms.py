from django import forms
from django.forms import inlineformset_factory
# Import model-model baru
from .models import Kios, KiosAllocation, Armada, FertilizerPrice, Kecamatan, JenisPupuk

# ==========================================
# FORM KIOS (Update: district -> kecamatan)
# ==========================================
class KiosForm(forms.ModelForm):
    class Meta:
        model = Kios
        # Perhatikan: 'district' diganti 'kecamatan'
        fields = ['name', 'pic_name', 'phone', 'kecamatan', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Kios'}),
            'pic_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Penanggung Jawab'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08xxx'}),
            'kecamatan': forms.Select(attrs={'class': 'form-select'}), # Dropdown otomatis dari Master Kecamatan
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ==========================================
# FORMSET ALOKASI (Update: fertilizer_type -> jenis_pupuk)
# ==========================================
KiosAllocationFormSet = inlineformset_factory(
    Kios, KiosAllocation,
    # Perhatikan: 'fertilizer_type' diganti 'jenis_pupuk'
    fields=('jenis_pupuk', 'year', 'quota_original'),
    extra=1, # Default 1 baris kosong
    can_delete=True,
    widgets={
        'jenis_pupuk': forms.Select(attrs={'class': 'form-select'}),
        'year': forms.NumberInput(attrs={'class': 'form-control'}),
        'quota_original': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton'}),
    }
)

# ==========================================
# FORM ARMADA (Update: photo_url -> image upload)
# ==========================================
class ArmadaForm(forms.ModelForm):
    class Meta:
        model = Armada
        fields = ['plate_number', 'vehicle_type', 'driver_name', 'photo_url', 'is_active']
        widgets = {
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Truk Engkel'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'photo_url': forms.FileInput(attrs={'class': 'form-control'}), # Ganti jadi FileInput
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ==========================================
# FORM HARGA (Hanya edit harga, jenis pupuk read-only di view)
# ==========================================
class HargaPupukForm(forms.ModelForm):
    class Meta:
        model = FertilizerPrice
        fields = ['price_buy', 'price_sell']
        widgets = {
            'price_buy': forms.NumberInput(attrs={'class': 'form-control', 'step': '100'}),
            'price_sell': forms.NumberInput(attrs={'class': 'form-control', 'step': '100'}),
        }