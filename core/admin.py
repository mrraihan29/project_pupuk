from django.contrib import admin
from .models import Kios, KiosAllocation, Armada, FertilizerPrice

# Konfigurasi Tampilan Kios di Admin
class KiosAllocationInline(admin.TabularInline):
    model = KiosAllocation
    extra = 1  # Menampilkan 1 baris kosong siap isi

@admin.register(Kios)
class KiosAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'pic_name', 'phone', 'is_active')
    search_fields = ('name', 'district')
    list_filter = ('district', 'is_active')
    inlines = [KiosAllocationInline] # Agar bisa input kuota langsung di halaman Kios

@admin.register(Armada)
class ArmadaAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'driver_name', 'vehicle_type', 'is_active')
    search_fields = ('plate_number', 'driver_name')

@admin.register(FertilizerPrice)
class PriceAdmin(admin.ModelAdmin):
    list_display = ('fertilizer_type', 'price_buy', 'price_sell', 'updated_at')