from django.contrib import admin
from .models import SalesOrder, StockCard

class StockCardInline(admin.TabularInline):
    model = StockCard
    extra = 0
    readonly_fields = ('date', 'trx_type', 'qty_change', 'balance_after', 'reference_number')
    can_delete = False # Audit log tidak boleh dihapus sembarangan

@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('so_code', 'fertilizer_type', 'tonnage_initial', 'tonnage_current', 'entry_date', 'maturity_date', 'is_closed')
    search_fields = ('so_code',)
    list_filter = ('fertilizer_type', 'is_closed', 'maturity_date')
    readonly_fields = ('fertilizer_type', 'tonnage_current', 'maturity_date') # Field ini otomatis, admin dilarang edit manual
    inlines = [StockCardInline] # Bisa lihat history mutasi langsung di detail SO

@admin.register(StockCard)
class StockCardAdmin(admin.ModelAdmin):
    list_display = ('date', 'sales_order', 'trx_type', 'qty_change', 'balance_after', 'reference_number')
    list_filter = ('trx_type', 'date')
    search_fields = ('reference_number', 'sales_order__so_code')
    
    # Mencegah manipulasi kartu stok manual lewat admin
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False