from django.contrib import admin
from .models import (
    CompanyProfile, Kecamatan, JenisPupuk, 
    Kios, KiosAllocation, Armada, FertilizerPrice
)

# ==========================================
# 1. MASTER DATA PENDUKUNG
# ==========================================
@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')

@admin.register(Kecamatan)
class KecamatanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'target_tonnage')
    search_fields = ('name',)

@admin.register(JenisPupuk)
class JenisPupukAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'color', 'is_active')
    list_editable = ('color', 'is_active')

# ==========================================
# 2. MASTER KIOS & ALOKASI
# ==========================================
class KiosAllocationInline(admin.TabularInline):
    model = KiosAllocation
    extra = 1

@admin.register(Kios)
class KiosAdmin(admin.ModelAdmin):
    # Update: district diganti kecamatan
    list_display = ('name', 'pic_name', 'kecamatan', 'phone', 'is_active')
    list_filter = ('kecamatan', 'is_active') 
    search_fields = ('name', 'pic_name')
    inlines = [KiosAllocationInline]

@admin.register(KiosAllocation)
class KiosAllocationAdmin(admin.ModelAdmin):
    # Update: fertilizer_type diganti jenis_pupuk
    list_display = ('kios', 'year', 'jenis_pupuk', 'quota_original', 'quota_remaining')
    list_filter = ('year', 'jenis_pupuk', 'kios__kecamatan')
    search_fields = ('kios__name',)

# ==========================================
# 3. MASTER ARMADA
# ==========================================
@admin.register(Armada)
class ArmadaAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'driver_name', 'vehicle_type', 'is_active')
    list_filter = ('vehicle_type', 'is_active')
    search_fields = ('plate_number', 'driver_name')

# ==========================================
# 4. MASTER HARGA
# ==========================================
@admin.register(FertilizerPrice)
class FertilizerPriceAdmin(admin.ModelAdmin):
    # Update: fertilizer_type diganti jenis_pupuk
    list_display = ('jenis_pupuk', 'price_buy', 'price_sell', 'updated_at')
    # Agar jenis_pupuk muncul nama-nya (bukan ID), Django otomatis handle via __str__ di model