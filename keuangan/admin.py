from django.contrib import admin
from .models import BiayaOperasional, Invoice, Payment

@admin.register(BiayaOperasional)
class BiayaOperasionalAdmin(admin.ModelAdmin):
    list_display = ('tanggal', 'kategori_utama', 'deskripsi', 'nominal')
    list_filter = ('kategori_utama', 'tanggal') # Update list_filter
    search_fields = ('deskripsi',)
    date_hierarchy = 'tanggal'

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('inv_number', 'distribution', 'issue_date', 'total_amount', 'status')
    list_filter = ('status', 'issue_date')
    search_fields = ('inv_number', 'distribution__kios__name')
    inlines = [PaymentInline]
    readonly_fields = ('inv_number', 'total_amount', 'total_paid', 'status')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'date', 'amount', 'method')