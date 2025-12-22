from django import forms
from .models import Payment, BiayaOperasional

# ==========================================
# 1. FORM PEMBAYARAN (INVOICE)
# ==========================================
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['date', 'amount', 'method', 'proof', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Rp ...'}),
            'method': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transfer BCA / Tunai'}),
            'proof': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catatan tambahan...'}),
        }

    def __init__(self, *args, **kwargs):
        self.invoice_obj = kwargs.pop('invoice', None) # Terima invoice dari view
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        # Validasi tambahan di level form agar pesan error lebih enak dibaca
        if self.invoice_obj:
            remaining = self.invoice_obj.remaining_balance
            if self.instance.pk: # Jika edit, tambahkan amount lama
                remaining += self.instance.amount
                
            if amount > remaining:
                raise forms.ValidationError(f"Jumlah melebihi sisa tagihan (Sisa: Rp {remaining:,.0f})")
        return amount

# ==========================================
# 2. FORM BIAYA OPERASIONAL
# ==========================================
class BiayaOperasionalForm(forms.ModelForm):
    class Meta:
        model = BiayaOperasional
        fields = ['tanggal', 'kategori_utama', 'deskripsi', 'nominal', 'bukti_foto']
        widgets = {
            'tanggal': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kategori_utama': forms.Select(attrs={'class': 'form-select'}),
            'deskripsi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Bensin Truk Nopol H-1234'}),
            'nominal': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Rp ...'}),
            'bukti_foto': forms.FileInput(attrs={'class': 'form-control'}),
        }