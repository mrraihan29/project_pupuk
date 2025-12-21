from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Prefetch
from datetime import date

from .models import Kios, Armada, FertilizerPrice
from .forms import KiosForm, KiosAllocationFormSet, ArmadaForm, HargaPupukForm
from gudang.models import SalesOrder, Distribution
from keuangan.models import Invoice, BiayaOperasional
import csv
from django.http import HttpResponse

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

# 5. DASHBOARD VIEW
@login_required
def dashboard(request):
    today = date.today()
    
    # --- 1. KEY METRICS (KARTU ATAS) ---
    
    # A. Total Piutang (Uang di luar)
    # Filter: Status UNPAID atau PARTIAL
    total_piutang = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL']
    ).aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0

    # B. Permintaan Belum Ditebus (Gap Alokasi vs SO)
    # Logika: Kita asumsikan target penebusan ideal adalah 100% Alokasi. 
    # Karena Alokasi ada di Kios, kita perlu agregat manual atau simplifikasi stok gudang saat ini.
    # Untuk dashboard ini, kita pakai "Total Stok Tersedia" sebagai indikator kesiapan.
    stok_npk = SalesOrder.objects.filter(fertilizer_type='NPK', is_closed=False).aggregate(Sum('tonnage_current'))['tonnage_current__sum'] or 0
    stok_urea = SalesOrder.objects.filter(fertilizer_type='UREA', is_closed=False).aggregate(Sum('tonnage_current'))['tonnage_current__sum'] or 0
    total_stok = stok_npk + stok_urea

    # C. Tagihan Jatuh Tempo (Risk Warning)
    # Invoice yang belum lunas DAN due_date <= hari ini
    invoice_overdue_count = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL'], 
        due_date__lte=today
    ).count()

    # --- 2. TABEL UTAMA (Sesuai Sketsa: No Inv, Kec, Kios, Piutang, Jatuh Tempo) ---
    # Kita ambil 10 Invoice yang belum lunas, urutkan dari yang paling tua (danger)
    invoices_list = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL']
    ).select_related('distribution__kios').order_by('due_date')[:10]

    # --- 3. SO JATUH TEMPO TERDEKAT (Sesuai Sketsa) ---
    # Sales Order yang stoknya masih ada (is_closed=False) tapi tanggal maturity sudah dekat
    so_expiring = SalesOrder.objects.filter(
        is_closed=False
    ).order_by('maturity_date')[:5] # Ambil 5 teratas

    context = {
        'total_piutang': total_piutang,
        'invoice_overdue_count': invoice_overdue_count,
        'stok_npk': stok_npk,
        'stok_urea': stok_urea,
        'total_stok': total_stok,
        'invoices_list': invoices_list,
        'so_expiring': so_expiring,
        'today': today,
    }

    return render(request, 'dashboard.html', context)


def raport_kios(request):
    """
    Laporan Kinerja Kios: Alokasi vs Realisasi Penyaluran.
    """
    current_year = date.today().year
    # Ambil semua Kios yang aktif beserta alokasi dan distribusi untuk menghindari query berulang
    kios_data = Kios.objects.filter(is_active=True).prefetch_related(
        'allocations',
        Prefetch('distributions', queryset=Distribution.objects.select_related('sales_order')),
    )

    report_data = []

    for k in kios_data:
        # Hitung per Kios
        # 1. Alokasi (Target)
        alloc_npk = k.allocations.filter(fertilizer_type='NPK', year=current_year).aggregate(Sum('quota_original'))['quota_original__sum'] or 0
        alloc_urea = k.allocations.filter(fertilizer_type='UREA', year=current_year).aggregate(Sum('quota_original'))['quota_original__sum'] or 0

        # 2. Realisasi Salur (Actual Distribution)
        # Kita cari distribusi ke kios ini di tahun 2025
        salur_npk = k.distributions.filter(sales_order__fertilizer_type='NPK', transaction_date__year=current_year).aggregate(Sum('tonnage_sent'))['tonnage_sent__sum'] or 0
        salur_urea = k.distributions.filter(sales_order__fertilizer_type='UREA', transaction_date__year=current_year).aggregate(Sum('tonnage_sent'))['tonnage_sent__sum'] or 0

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

@login_required
def master_harga(request):
    # Kita asumsikan hanya ada 2 baris data di database: NPK dan UREA
    # Jika belum ada, kita create dulu (Safety logic)
    # Harga disimpan per ton (bukan per kg) untuk hindari faktor 1000 di perhitungan
    npk_obj, _ = FertilizerPrice.objects.get_or_create(
        fertilizer_type='NPK', defaults={'price_buy': 2300000, 'price_sell': 2350000}
    )
    urea_obj, _ = FertilizerPrice.objects.get_or_create(
        fertilizer_type='UREA', defaults={'price_buy': 2200000, 'price_sell': 2250000}
    )

    if request.method == 'POST':
        # Kita handle 2 form dalam 1 halaman (Prefix digunakan agar input tidak bentrok)
        form_npk = HargaPupukForm(request.POST, instance=npk_obj, prefix='npk')
        form_urea = HargaPupukForm(request.POST, instance=urea_obj, prefix='urea')
        
        if form_npk.is_valid() and form_urea.is_valid():
            form_npk.save()
            form_urea.save()
            messages.success(request, "Harga Pupuk Berhasil Diupdate!")
            return redirect('master_harga')
    else:
        form_npk = HargaPupukForm(instance=npk_obj, prefix='npk')
        form_urea = HargaPupukForm(instance=urea_obj, prefix='urea')

    return render(request, 'core/master_harga.html', {
        'form_npk': form_npk,
        'form_urea': form_urea
    })
    
# --- FUNGSI BANTUAN: EXPORT KE CSV/EXCEL ---
def export_laporan_xls(start_date, end_date, data):
    """
    Fungsi khusus untuk generate file CSV yang bisa dibuka Excel.
    """
    response = HttpResponse(content_type='text/csv')
    # Nama file dinamis sesuai tanggal
    filename = f"Laporan_Keuangan_{start_date}_sd_{end_date}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    
    # HEADER
    writer.writerow(['LAPORAN KEUANGAN & LABA RUGI (SIM BADA TANI)'])
    writer.writerow([f'Periode: {start_date} s/d {end_date}'])
    writer.writerow([]) # Baris kosong

    # BODY LAPORAN
    writer.writerow(['URAIAN', 'DETAIL', 'NILAI (Rp)'])
    
    # 1. PENDAPATAN (OMZET)
    writer.writerow(['1. OMZET PENJUALAN (Penyaluran)'])
    writer.writerow(['', 'NPK', data['omzet_npk']])
    writer.writerow(['', 'UREA', data['omzet_urea']])
    writer.writerow(['', 'TOTAL OMZET', data['total_omzet']])
    writer.writerow([])

    # 2. PENGELUARAN POKOK (MODAL BELI)
    writer.writerow(['2. HARGA POKOK PENEBUSAN (Modal)'])
    writer.writerow(['', 'NPK', data['modal_npk']])
    writer.writerow(['', 'UREA', data['modal_urea']])
    writer.writerow(['', 'TOTAL MODAL', data['total_modal']])
    writer.writerow([])
    
    # LABA KOTOR
    writer.writerow(['LABA KOTOR (Omzet - Modal)', '', data['gross_profit']])
    writer.writerow([])
    
    # 3. BIAYA OPERASIONAL
    writer.writerow(['3. BIAYA OPERASIONAL'])
    writer.writerow(['', 'Biaya Armada (Bensin/Servis/Tol)', data['ops_armada']])
    writer.writerow(['', 'Biaya Kantor (Gaji/Listrik/Makan/Lainnya)', data['ops_kantor']])
    writer.writerow(['', 'TOTAL BIAYA', data['total_ops']])
    writer.writerow([])

    # 4. HASIL AKHIR
    writer.writerow(['LABA BERSIH (NET PROFIT)', '', data['net_profit']])
    writer.writerow([])
    writer.writerow([])

    # 5. INFO TAMBAHAN (VALUASI ASET)
    writer.writerow(['INFO: VALUASI SISA STOK GUDANG (ASET)'])
    writer.writerow(['', 'Estimasi Nilai Stok NPK', data['aset_npk']])
    writer.writerow(['', 'Estimasi Nilai Stok UREA', data['aset_urea']])
    writer.writerow(['', 'TOTAL ASET', data['total_aset']])

    return response

# --- VIEW UTAMA: HALAMAN LAPORAN ---
@login_required
def laporan_keuangan(request):
    # 1. SETUP TANGGAL (Default: Tanggal 1 bulan ini s/d Hari Ini)
    today = date.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    default_end = today.strftime('%Y-%m-%d')

    start_date = request.GET.get('start', default_start)
    end_date = request.GET.get('end', default_end)

    # 2. AMBIL MASTER HARGA (Sebagai Acuan Valuasi)
    # Gunakan get_or_create agar tidak error jika data kosong
    # Harga disimpan per ton
    harga_npk, _ = FertilizerPrice.objects.get_or_create(
        fertilizer_type='NPK', defaults={'price_buy': 2300000, 'price_sell': 2350000}
    )
    harga_urea, _ = FertilizerPrice.objects.get_or_create(
        fertilizer_type='UREA', defaults={'price_buy': 2200000, 'price_sell': 2250000}
    )

    # 3. HITUNG MODAL (PENEBUSAN / BELI)
    # Logic: Berapa ton kita beli (SalesOrder) dalam periode ini?
    # Filter: entry_date
    qty_beli_npk = SalesOrder.objects.filter(
        entry_date__range=[start_date, end_date], 
        fertilizer_type='NPK'
    ).aggregate(total=Sum('tonnage_initial'))['total'] or 0
    
    qty_beli_urea = SalesOrder.objects.filter(
        entry_date__range=[start_date, end_date], 
        fertilizer_type='UREA'
    ).aggregate(total=Sum('tonnage_initial'))['total'] or 0

    modal_npk = qty_beli_npk * harga_npk.price_buy
    modal_urea = qty_beli_urea * harga_urea.price_buy
    total_modal = modal_npk + modal_urea

    # 4. HITUNG OMZET (PENYALURAN / JUAL)
    # Logic: Berapa ton kita jual (Distribution) dalam periode ini?
    # Filter: transaction_date
    qty_jual_npk = Distribution.objects.filter(
        transaction_date__range=[start_date, end_date],
        sales_order__fertilizer_type='NPK'
    ).aggregate(total=Sum('tonnage_sent'))['total'] or 0

    qty_jual_urea = Distribution.objects.filter(
        transaction_date__range=[start_date, end_date],
        sales_order__fertilizer_type='UREA'
    ).aggregate(total=Sum('tonnage_sent'))['total'] or 0

    omzet_npk = qty_jual_npk * harga_npk.price_sell
    omzet_urea = qty_jual_urea * harga_urea.price_sell
    total_omzet = omzet_npk + omzet_urea

# 5. HITUNG BIAYA OPERASIONAL (UPDATE LOGIC BARU)
    
    # Logic Lama: Filter berdasarkan 'kategori__in' (Nama field lama)
    # Logic Baru: Filter berdasarkan 'kategori_utama' (Nama field baru)
    
    # Biaya Armada (Langsung filter kategori_utama='ARMADA')
    biaya_armada = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        kategori_utama='ARMADA'  # Field Baru
    ).aggregate(total=Sum('nominal'))['total'] or 0

    # Biaya Kantor (Langsung filter kategori_utama='KANTOR')
    biaya_kantor = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        kategori_utama='KANTOR'  # Field Baru
    ).aggregate(total=Sum('nominal'))['total'] or 0
    
    total_ops = biaya_armada + biaya_kantor

    # 6. HITUNG PROFIT
    gross_profit = total_omzet - total_modal
    net_profit = gross_profit - total_ops

    # 7. VALUASI ASET (SISA STOK GUDANG SAAT INI)
    # Ini stok real-time, tidak terpengaruh filter tanggal (snapshot hari ini)
    stok_sisa_npk = SalesOrder.objects.filter(is_closed=False, fertilizer_type='NPK').aggregate(total=Sum('tonnage_current'))['total'] or 0
    stok_sisa_urea = SalesOrder.objects.filter(is_closed=False, fertilizer_type='UREA').aggregate(total=Sum('tonnage_current'))['total'] or 0

    aset_npk = stok_sisa_npk * harga_npk.price_buy
    aset_urea = stok_sisa_urea * harga_urea.price_buy
    total_aset = aset_npk + aset_urea

    # --- BUNGKUS DATA (CONTEXT) ---
    context_data = {
        # Data Omzet
        'omzet_npk': omzet_npk,
        'omzet_urea': omzet_urea,
        'total_omzet': total_omzet,
        
        # Data Modal
        'modal_npk': modal_npk,
        'modal_urea': modal_urea,
        'total_modal': total_modal,
        
        # Profitability
        'gross_profit': gross_profit,
        
        # Operasional
        'ops_armada': biaya_armada,
        'ops_kantor': biaya_kantor,
        'total_ops': total_ops,
        
        # Final
        'net_profit': net_profit,
        
        # Aset
        'aset_npk': aset_npk,
        'aset_urea': aset_urea,
        'total_aset': total_aset,
        
        # Filter Info
        'start_date': start_date,
        'end_date': end_date
    }

    # --- LOGIC EXPORT ---
    if request.GET.get('export') == 'xls':
        return export_laporan_xls(start_date, end_date, context_data)

    # --- RENDER HTML ---
    return render(request, 'core/laporan_keuangan.html', context_data)