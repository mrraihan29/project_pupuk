from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Prefetch

# Import Models & Forms Baru
from .models import SalesOrder, SalesOrderAllocation, Distribution, WarehouseTransfer, StockCard
from .forms import (
    SalesOrderForm, AllocationFormSet, 
    DistributionForm, WarehouseTransferForm, 
    StockOpnameForm
)

# ==========================================
# 1. MODUL PENEBUSAN (SO)
# ==========================================
@login_required
def so_list(request):
    """
    Daftar Sales Order (Stok Virtual).
    Menggunakan prefetch_related untuk mengambil detail alokasi dalam 1 query efisien.
    """
    orders = SalesOrder.objects.select_related('jenis_pupuk') \
                            .prefetch_related('allocations__kecamatan') \
                            .order_by('-date')
    
    return render(request, 'gudang/so_list.html', {'orders': orders})

@login_required
def so_create(request):
    """
    Input SO Baru dengan Multi-Kecamatan (Dynamic Formset).
    Menggunakan Atomic Transaction untuk keamanan data.
    """
    if request.method == 'POST':
        form = SalesOrderForm(request.POST, request.FILES)
        formset = AllocationFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic(): # === TITIK KRITIKAL KEAMANAN DATA ===
                    # 1. Simpan Header SO
                    so = form.save()
                    
                    # 2. Simpan Detail Alokasi
                    allocations = formset.save(commit=False)
                    for alloc in allocations:
                        alloc.sales_order = so
                        alloc.save()
                    
                    # (Signal di gudang/signals.py akan otomatis mencatat Kartu Stok)
                    
                    messages.success(request, f"Penebusan SO {so.so_number} berhasil disimpan!")
                    return redirect('so_list')
                    
            except Exception as e:
                # Tangkap error database jika ada
                messages.error(request, f"Terjadi kesalahan database: {e}")
        else:
            messages.error(request, "Gagal menyimpan. Periksa inputan bertanda merah.")
    else:
        form = SalesOrderForm()
        formset = AllocationFormSet()
    
    return render(request, 'gudang/so_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Input Penebusan (SO)'
    })

# ==========================================
# 2. MODUL TRANSFER (TARIK KE GUDANG)
# ==========================================
@login_required
def transfer_list(request):
    """Riwayat Perpindahan Stok (Virtual -> Fisik)"""
    transfers = WarehouseTransfer.objects.select_related('source_so__jenis_pupuk') \
                                         .order_by('-date')
    return render(request, 'gudang/transfer_list.html', {'transfers': transfers})

@login_required
def transfer_create(request):
    """Form menarik stok dari Virtual SO ke Fisik Gudang"""
    if request.method == 'POST':
        form = WarehouseTransferForm(request.POST)
        if form.is_valid():
            try:
                # Validasi logika (Cukup stok kah?) sudah ditangani di models.py clean()
                # Form.is_valid() otomatis memanggil clean() tersebut.
                form.save()
                
                messages.success(request, "Stok berhasil ditarik ke Gudang Fisik!")
                return redirect('transfer_list') # Redirect ke list transfer
            except Exception as e:
                messages.error(request, f"Error: {e}")
        else:
            # Error validasi (misal: stok kurang) akan muncul otomatis di template via {{ form.errors }}
            messages.error(request, "Gagal menarik stok. Periksa pesan error di bawah.")
    else:
        form = WarehouseTransferForm()
    
    return render(request, 'gudang/transfer_form.html', {'form': form, 'title': 'Tarik Stok ke Gudang'})

# ==========================================
# 3. MODUL DISTRIBUSI (SURAT JALAN)
# ==========================================
@login_required
def distribution_list(request):
    """Daftar Surat Jalan"""
    # Optimasi Query: Ambil data Kios, Armada, dan SO sekaligus
    dist_list = Distribution.objects.select_related('kios', 'armada', 'source_so', 'jenis_pupuk') \
                                    .order_by('-date', '-created_at')
    
    return render(request, 'gudang/distribution_list.html', {'dist_list': dist_list})

@login_required
def distribution_create(request):
    if request.method == 'POST':
        form = DistributionForm(request.POST)
        if form.is_valid():
            try:
                dist = form.save()
                messages.success(request, f"Surat Jalan {dist.no_surat_jalan} berhasil diterbitkan.")
                return redirect('distribution_list')
            except Exception as e:
                messages.error(request, f"Gagal Simpan: {e}")
        else:
            messages.error(request, "Form tidak valid. Cek apakah Stok Cukup?")
    else:
        form = DistributionForm()

    return render(request, 'gudang/distribution_form.html', {'form': form})

# ==========================================
# 4. MODUL KARTU STOK & OPNAME
# ==========================================
@login_required
def stock_card_list(request):
    """
    Laporan Kartu Stok (Ledger) - Single Source of Truth
    """
    stocks = StockCard.objects.select_related('jenis_pupuk') \
                            .order_by('-date', '-created_at')
    
    # Filter sederhana (Opsional, bisa dikembangkan)
    jenis_filter = request.GET.get('jenis')
    if jenis_filter:
        stocks = stocks.filter(jenis_pupuk__id=jenis_filter)

    return render(request, 'gudang/stock_card_list.html', {'stocks': stocks})

@login_required
def stock_opname(request):
    """
    Input Penyesuaian Stok Manual (Placeholder)
    Fitur ini akan dikembangkan lebih lanjut nanti.
    """
    if request.method == 'POST':
        form = StockOpnameForm(request.POST)
        if form.is_valid():
            # TODO: Implementasi logika Opname (Hitung selisih -> Buat Transaksi Adjustment)
            messages.info(request, "Fitur Opname sedang dalam pengembangan logic balance.")
            return redirect('stock_card_list')
    else:
        form = StockOpnameForm()
    
    return render(request, 'gudang/stock_opname.html', {'form': form})