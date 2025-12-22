from django.contrib import admin
from .models import SalesOrder, SalesOrderAllocation, WarehouseTransfer, Distribution, StockCard

class AllocationInline(admin.TabularInline):
    model = SalesOrderAllocation
    extra = 1

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_number', 'date', 'jenis_pupuk', 'total_tonnage', 'is_closed')
    inlines = [AllocationInline]
    list_filter = ('jenis_pupuk', 'is_closed')
    search_fields = ('so_number',)

@admin.register(WarehouseTransfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('date', 'source_so', 'tonnage', 'reference_code')

@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    list_display = ('no_surat_jalan', 'date', 'kios', 'source_type', 'tonnage')
    list_filter = ('source_type', 'date')

@admin.register(StockCard)
class StockCardAdmin(admin.ModelAdmin):
    list_display = ('date', 'stock_type', 'transaction_type', 'reference_number', 'qty_in', 'qty_out', 'jenis_pupuk')
    list_filter = ('stock_type', 'transaction_type', 'jenis_pupuk')
    readonly_fields = ('qty_in', 'qty_out', 'balance', 'reference_number') # Agar tidak diedit manual sembarangan