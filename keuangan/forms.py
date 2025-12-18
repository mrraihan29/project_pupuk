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
        fields = ['armada', 'kategori', 'nominal', 'tanggal', 'keterangan', 'foto_bukti']
        widgets = {
            'armada': forms.Select(attrs={'class': 'form-select'}),
            'kategori': forms.Select(attrs={'class': 'form-select'}),
            'nominal': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Rp'}),
            'tanggal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'keterangan': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'foto_bukti': forms.FileInput(attrs={'class': 'form-control'}),
        }