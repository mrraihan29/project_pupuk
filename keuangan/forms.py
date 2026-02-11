from django import forms
from .models import Payment, Invoice, BiayaOperasional
from decimal import Decimal
# ==========================================
# 1. FORM PEMBAYARAN (INVOICE)
# ==========================================
class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['date', 'amount', 'method', 'proof', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': 'Rp ...', 'inputmode': 'decimal'}),
            'method': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transfer BCA / Tunai'}),
            'proof': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catatan tambahan...'}),
        }

    def __init__(self, *args, **kwargs):
        # Ambil invoice yang dikirim dari views.py
        self.invoice_obj = kwargs.pop('invoice', None) 
        super().__init__(*args, **kwargs)
        
        # ===>>> PERBAIKAN DI SINI <<<===
        # Tempelkan invoice ke instance model SEBELUM validasi berjalan
        # Agar model.clean() bisa mengakses self.invoice
        if self.invoice_obj:
            self.instance.invoice = self.invoice_obj

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.invoice_obj:
            # Gunakan remaining_balance property
            remaining = self.invoice_obj.remaining_balance or Decimal('0')
            
            # Jika sedang edit (pk ada), kembalikan saldo sebelumnya agar hitungan benar
            if self.instance.pk: 
                remaining += self.instance.amount or Decimal('0')
                
            if amount > remaining:
                raise forms.ValidationError(f"Jumlah melebihi sisa tagihan (Sisa: Rp {remaining:,.0f})")
        return amount

# ==========================================
# 2. FORM BIAYA OPERASIONAL
# ==========================================
class InvoiceEditForm(forms.ModelForm):
    """Form untuk superadmin mengedit tanggal invoice."""
    class Meta:
        model = Invoice
        fields = ['issue_date', 'due_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        issue = cleaned.get('issue_date')
        due = cleaned.get('due_date')
        if issue and due and due < issue:
            raise forms.ValidationError("Tanggal jatuh tempo tidak boleh sebelum tanggal terbit.")
        return cleaned


class BiayaOperasionalForm(forms.ModelForm):
    class Meta:
        model = BiayaOperasional
        fields = ['tanggal', 'kategori_utama', 'kabupaten', 'armada', 'deskripsi', 'nominal', 'bukti_foto']
        widgets = {
            'tanggal': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kategori_utama': forms.Select(attrs={'class': 'form-select'}),
            'kabupaten': forms.Select(attrs={'class': 'form-select'}),
            'armada': forms.Select(attrs={'class': 'form-select'}),  # tambahkan ini
            'deskripsi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Bensin Truk Nopol H-1234'}),
            'nominal': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': 'Rp ...', 'inputmode': 'decimal'}),
            'bukti_foto': forms.FileInput(attrs={'class': 'form-control'}),
        }