from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Kios, Armada
from .forms import KiosForm, KiosAllocationFormSet, ArmadaForm
from django.db.models import Sum, F
from gudang.models import SalesOrder
from keuangan.models import Invoice
from datetime import date

# 1. READ (Daftar Kios)
def kios_list(request):
    kios_data = Kios.objects.all().order_by('-created_at')
    return render(request, 'core/kios_list.html', {'kios_data': kios_data})

# 2. CREATE (Tambah Kios Baru)
def kios_create(request):
    if request.method == 'POST':
        form = KiosForm(request.POST)
        formset = KiosAllocationFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            kios = form.save() # Simpan Induk (Kios)
            
            # Simpan Anak (Alokasi)
            allocations = formset.save(commit=False)
            for allocation in allocations:
                allocation.kios = kios # Sambungkan anak ke induk
                allocation.quota_remaining = allocation.quota_original # Set sisa = awal
                allocation.save()
            
            messages.success(request, f"Kios {kios.name} berhasil dibuat!")
            return redirect('kios_list')
    else:
        form = KiosForm()
        formset = KiosAllocationFormSet()

    return render(request, 'core/kios_form.html', {
        'form': form, 
        'formset': formset, 
        'title': 'Tambah Kios Baru'
    })

# 3. UPDATE (Edit Kios)
def kios_update(request, pk):
    kios = get_object_or_404(Kios, pk=pk)
    
    if request.method == 'POST':
        form = KiosForm(request.POST, instance=kios)
        formset = KiosAllocationFormSet(request.POST, instance=kios)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save() # Otomatis update karena sudah ada instance
            messages.success(request, "Data Kios berhasil diperbarui.")
            return redirect('kios_list')
    else:
        form = KiosForm(instance=kios)
        formset = KiosAllocationFormSet(instance=kios)

    return render(request, 'core/kios_form.html', {
        'form': form, 
        'formset': formset, 
        'title': f'Edit Kios: {kios.name}'
    })

# 4. DELETE (Hapus Kios)
def kios_delete(request, pk):
    kios = get_object_or_404(Kios, pk=pk)
    if request.method == 'POST':
        kios.delete()
        messages.success(request, "Kios berhasil dihapus.")
        return redirect('kios_list')
    
    return render(request, 'core/kios_confirm_delete.html', {'kios': kios})

# --- DASHBOARD (View Lama) ---
def dashboard(request):
    # 1. Total Stok Gudang (Real-time)
    stok_npk = SalesOrder.objects.filter(fertilizer_type='NPK', is_closed=False).aggregate(Sum('tonnage_current'))['tonnage_current__sum'] or 0
    stok_urea = SalesOrder.objects.filter(fertilizer_type='UREA', is_closed=False).aggregate(Sum('tonnage_current'))['tonnage_current__sum'] or 0

    # 2. Keuangan (Invoice Overdue / Macet)
    today = date.today()
    # Cari invoice UNPAID yang tanggal jatuh temponya sudah lewat hari ini
    tagihan_macet = Invoice.objects.filter(status='UNPAID', due_date__lt=today).count()
    total_piutang = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0

    # 3. Peringatan Stok SO Expired (Jatuh Tempo Gudang)
    # Cari SO yang belum habis TAPI sudah lewat maturity_date
    so_expired = SalesOrder.objects.filter(is_closed=False, maturity_date__lt=today).count()

    context = {
        'stok_npk': stok_npk,
        'stok_urea': stok_urea,
        'tagihan_macet': tagihan_macet,
        'total_piutang': total_piutang,
        'so_expired': so_expired,
    }
    return render(request, 'dashboard.html', context)


def raport_kios(request):
    """
    Laporan Kinerja Kios: Alokasi vs Realisasi Penyaluran.
    """
    # Ambil semua Kios yang aktif
    kios_data = Kios.objects.filter(is_active=True).prefetch_related('allocations')

    report_data = []

    for k in kios_data:
        # Hitung per Kios
        # 1. Alokasi (Target)
        alloc_npk = k.allocations.filter(fertilizer_type='NPK', year=2025).aggregate(Sum('quota_original'))['quota_original__sum'] or 0
        alloc_urea = k.allocations.filter(fertilizer_type='UREA', year=2025).aggregate(Sum('quota_original'))['quota_original__sum'] or 0

        # 2. Realisasi Salur (Actual Distribution)
        # Kita cari distribusi ke kios ini di tahun 2025
        salur_npk = k.distributions.filter(sales_order__fertilizer_type='NPK', transaction_date__year=2025).aggregate(Sum('tonnage_sent'))['tonnage_sent__sum'] or 0
        salur_urea = k.distributions.filter(sales_order__fertilizer_type='UREA', transaction_date__year=2025).aggregate(Sum('tonnage_sent'))['tonnage_sent__sum'] or 0

        # 3. Hitung % Capaian
        persen_npk = (salur_npk / alloc_npk * 100) if alloc_npk > 0 else 0
        persen_urea = (salur_urea / alloc_urea * 100) if alloc_urea > 0 else 0

        report_data.append({
            'name': k.name,
            'district': k.district,
            'npk': {'target': alloc_npk, 'real': salur_npk, 'persen': persen_npk},
            'urea': {'target': alloc_urea, 'real': salur_urea, 'persen': persen_urea},
        })

    return render(request, 'core/raport_kios.html', {'report': report_data})

def armada_list(request):
    armada = Armada.objects.all()
    return render(request, 'core/armada_list.html', {'armada': armada})

def armada_create(request):
    if request.method == 'POST':
        form = ArmadaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Armada berhasil ditambahkan.")
            return redirect('armada_list')
    else:
        form = ArmadaForm()
    return render(request, 'core/armada_form.html', {'form': form})