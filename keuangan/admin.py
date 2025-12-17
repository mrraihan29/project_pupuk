from django.contrib import admin
from .models import Invoice, Payment, BiayaOperasional

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'kios_name', 'total_amount', 'remaining_balance', 'status', 'due_date')
    list_filter = ('status', 'due_date')
    search_fields = ('invoice_no', 'distribution__kios__name')
    inlines = [PaymentInline] # Bisa input bayar langsung di detail invoice

    @admin.display(description='Kios')
    def kios_name(self, obj):
        return obj.distribution.kios.name

@admin.register(BiayaOperasional)
class OpsAdmin(admin.ModelAdmin):
    list_display = ('tanggal', 'armada', 'kategori', 'nominal', 'is_approved')
    list_filter = ('kategori', 'is_approved', 'armada')