from django import forms
from django.forms import inlineformset_factory
from .models import Kios, KiosAllocation

class KiosForm(forms.ModelForm):
    class Meta:
        model = Kios
        fields = ['name', 'pic_name', 'phone', 'district', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Kios'}),
            'pic_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Pemilik'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08xxx'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kecamatan'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# --- FORMSET (Untuk Input Alokasi NPK & Urea Sekaligus) ---
# Ini membuat form anak yang menempel pada form Kios
KiosAllocationFormSet = inlineformset_factory(
    Kios, KiosAllocation,
    fields=('fertilizer_type', 'year', 'quota_original'),
    extra=2, # Munculkan 2 baris kosong (Untuk NPK & UREA)
    can_delete=False,
    widgets={
        'fertilizer_type': forms.Select(attrs={'class': 'form-select'}),
        'year': forms.NumberInput(attrs={'class': 'form-control'}),
        'quota_original': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ton'}),
    }
)