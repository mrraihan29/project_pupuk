from django import forms
from .models import Payment, BiayaOperasional

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        # HAPUS 'payment_method' DARI SINI:
        fields = ['amount', 'payment_date', 'proof_image', 'notes'] 
        
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Rp'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'proof_image': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Bank / Keterangan'}),
        }

class BiayaOperasionalForm(forms.ModelForm):
    class Meta:
        model = BiayaOperasional
        # KITA PAKAI NAMA FIELD BARU SESUAI MODELS.PY
        fields = [
            'tanggal', 
            'kategori_utama',  # Dulu: kategori
            'jenis_biaya',     # Baru
            'armada', 
            'nominal', 
            'urgensi',         # Baru
            'status',          # Baru
            'description',     # Dulu: keterangan
            'bukti_foto'       # Dulu: foto_bukti
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'kategori_utama': forms.Select(attrs={'class': 'form-select', 'id': 'id_kategori_utama'}),
            'jenis_biaya': forms.Select(attrs={'class': 'form-select'}),
            'armada': forms.Select(attrs={'class': 'form-select', 'id': 'id_armada_container'}),
            'nominal': forms.NumberInput(attrs={'class': 'form-control'}),
            'urgensi': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Jelaskan detail pengeluaran...'}),
            'bukti_foto': forms.FileInput(attrs={'class': 'form-control'}),
        }