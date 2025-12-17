from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Sum
from core.models import Kios, KiosAllocation
from .models import SalesOrder
from .forms import DistributionForm

# --- VIEW UTAMA ---
def distribution_create(request):
    if request.method == 'POST':
        form = DistributionForm(request.POST)
        if form.is_valid():
            dist = form.save()
            messages.success(request, f"Penyaluran Berhasil! Surat Jalan: {dist.surat_jalan_no}")
            return redirect('dashboard') # Nanti kita arahkan ke list distribusi
    else:
        form = DistributionForm()

    return render(request, 'gudang/distribution_form.html', {'form': form})

# --- API HELPER (Untuk AJAX JavaScript) ---
def get_kios_info(request):
    """
    API ini dipanggil saat Admin memilih Kios di dropdown.
    Mengembalikan data: Alamat, PIC, Sisa Kuota Kios, & Sisa Kuota Kecamatan.
    """
    kios_id = request.GET.get('kios_id')
    
    try:
        kios = Kios.objects.get(id=kios_id)
        
        # Hitung Kuota per Jenis
        # Format return: { 'NPK': {'kios': 10, 'district': 50}, 'UREA': ... }
        allocations = {}
        for f_type in ['NPK', 'UREA']:
            # 1. Kuota Kios Ini
            try:
                kios_alloc = KiosAllocation.objects.get(kios=kios, fertilizer_type=f_type, year=2025) # Harusnya dinamis tahunnya
                k_rem = kios_alloc.quota_remaining
            except KiosAllocation.DoesNotExist:
                k_rem = 0
            
            # 2. Kuota Satu Kecamatan (Untuk Fluid Allocation)
            d_rem = KiosAllocation.objects.filter(
                kios__district=kios.district,
                fertilizer_type=f_type,
                year=2025
            ).aggregate(Sum('quota_remaining'))['quota_remaining__sum'] or 0
            
            allocations[f_type] = {
                'kios_remaining': float(k_rem),
                'district_remaining': float(d_rem)
            }

        data = {
            'address': kios.address,
            'district': kios.district,
            'pic': kios.pic_name,
            'allocations': allocations
        }
        return JsonResponse(data)
        
    except Kios.DoesNotExist:
        return JsonResponse({'error': 'Kios not found'}, status=404)

def get_so_info(request):
    """
    API untuk mengambil data stok & jenis pupuk dari SO yang dipilih
    """
    so_id = request.GET.get('so_id')
    try:
        so = SalesOrder.objects.get(id=so_id)
        return JsonResponse({
            'fertilizer_type': so.fertilizer_type,
            'current_stock': float(so.tonnage_current)
        })
    except SalesOrder.DoesNotExist:
        return JsonResponse({'error': 'SO not found'}, status=404)