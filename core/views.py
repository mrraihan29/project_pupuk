from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Prefetch, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date
import csv
from django.http import HttpResponse

# Import Models Baru
from .models import Kios, Armada, FertilizerPrice, JenisPupuk, Kecamatan, KiosAllocation
from .forms import KiosForm, KiosAllocationFormSet, ArmadaForm, HargaPupukForm
from gudang.models import SalesOrder, SalesOrderAllocation, Distribution, StockCard
from keuangan.models import Invoice, BiayaOperasional

# 1. READ (Daftar Kios)
@login_required
def kios_list(request):
    # Select related kecamatan agar query efisien
    current_year = date.today().year
    kios_data = Kios.objects.select_related('kecamatan').prefetch_related('allocations__jenis_pupuk').order_by('-created_at')

    # Hitung realisasi distribusi per kios x jenis pupuk di tahun berjalan
    kios_ids = [k.id for k in kios_data]
    dist_map = {}
    if kios_ids:
        dist_agg = Distribution.objects.filter(
            kios_id__in=kios_ids,
            date__year=current_year
        ).values('kios_id', 'jenis_pupuk_id').annotate(total=Sum('tonnage'))

        for row in dist_agg:
            dist_map[(row['kios_id'], row['jenis_pupuk_id'])] = row['total'] or Decimal('0')

    # Tempelkan nilai realisasi ke setiap allocation agar template sederhana
    for kios in kios_data:
        for allocation in kios.allocations.all():
            allocation.realized = dist_map.get((kios.id, allocation.jenis_pupuk_id), Decimal('0'))

    return render(request, 'core/kios_list.html', {
        'kios_data': kios_data,
        'current_year': current_year,
    })

# 2. CREATE (Tambah Kios Baru)
@login_required
def kios_create(request):
    if request.method == 'POST':
        form = KiosForm(request.POST)
        formset = KiosAllocationFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            kios = form.save()
            
            allocations = formset.save(commit=False)
            for allocation in allocations:
                allocation.kios = kios
                allocation.quota_remaining = allocation.quota_original
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
@login_required
def kios_update(request, pk):
    kios = get_object_or_404(Kios, pk=pk)
    
    if request.method == 'POST':
        form = KiosForm(request.POST, instance=kios)
        formset = KiosAllocationFormSet(request.POST, instance=kios)
        
        if form.is_valid() and formset.is_valid():
            form.save()

            allocations = formset.save(commit=False)

            # Hapus baris yang ditandai delete di formset
            for obj in formset.deleted_objects:
                obj.delete()

            for allocation in allocations:
                allocation.kios = kios
                # Pastikan alokasi baru punya sisa sama dengan jatah awal
                if allocation.pk is None:
                    allocation.quota_remaining = allocation.quota_original
                allocation.save()
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
@login_required
def kios_delete(request, pk):
    kios = get_object_or_404(Kios, pk=pk)
    if request.method == 'POST':
        kios.delete()
        messages.success(request, "Kios berhasil dihapus.")
        return redirect('kios_list')
    
    return render(request, 'core/kios_confirm_delete.html', {'kios': kios})

# ==========================================
# DASHBOARD VIEW (FIXED)
# ==========================================
@login_required
def dashboard(request):
    today = date.today()
    
    # 1. HITUNG UANG (FIXED: Tambahkan output_field)
    piutang_data = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(
        total_sisa=Sum(
            F('total_amount') - F('total_paid'), 
            output_field=DecimalField() # <--- WAJIB ADA
        )
    )
    total_piutang = piutang_data['total_sisa'] or 0

    # 2. HITUNG STOK TERPISAH (FIXED: Tambahkan output_field pada Coalesce)
    def get_stock_balance(jenis_nama, tipe_stok):
        val = StockCard.objects.filter(
            jenis_pupuk__name=jenis_nama,
            stock_type=tipe_stok
        ).aggregate(
            # Logic: (Total Masuk atau 0) - (Total Keluar atau 0)
            # Kita paksa 0 dianggap DecimalField agar tidak error mixed types
            saldo=Coalesce(Sum('qty_in'), 0, output_field=DecimalField()) - 
                  Coalesce(Sum('qty_out'), 0, output_field=DecimalField())
        )['saldo']
        
        return val if val is not None else 0

    # -- Stok Virtual (Masih di Pabrik) --
    virt_npk = get_stock_balance('NPK', 'VIRTUAL')
    virt_urea = get_stock_balance('UREA', 'VIRTUAL')
    
    # -- Stok Fisik (Siap Kirim di Gudang) --
    phys_npk = get_stock_balance('NPK', 'PHYSICAL')
    phys_urea = get_stock_balance('UREA', 'PHYSICAL')

    # 3. DATA LAINNYA
    invoice_overdue_count = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL'], 
        due_date__lte=today
    ).count()

    invoices_list = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']) \
                                    .select_related('distribution__kios') \
                                    .order_by('due_date')[:5]

    so_expiring = SalesOrder.objects.filter(is_closed=False).order_by('date')[:5]

    context = {
        'total_piutang': total_piutang,
        'invoice_overdue_count': invoice_overdue_count,
        
        # Kirim data terpisah ke HTML
        'virt_npk': virt_npk,
        'virt_urea': virt_urea,
        'phys_npk': phys_npk,
        'phys_urea': phys_urea,
        
        'invoices_list': invoices_list,
        'so_expiring': so_expiring,
        'today': today,
    }

    return render(request, 'dashboard.html', context)


@login_required
def raport_kios(request):
    """
    Laporan Kinerja Kios: Alokasi vs Realisasi.
    """
    current_year = date.today().year
    kios_data = Kios.objects.filter(is_active=True).prefetch_related('allocations', 'kecamatan')
    report_data = []

    for k in kios_data:
        # Alokasi (Target) - Menggunakan relation ke JenisPupuk
        alloc_npk = k.allocations.filter(jenis_pupuk__name='NPK', year=current_year).aggregate(Sum('quota_original'))['quota_original__sum'] or 0
        alloc_urea = k.allocations.filter(jenis_pupuk__name='UREA', year=current_year).aggregate(Sum('quota_original'))['quota_original__sum'] or 0

        # Realisasi (Actual) - Menggunakan relation Distribution -> JenisPupuk
        # Perhatikan path filter: distribution -> jenis_pupuk__name
        dist_npk = Distribution.objects.filter(kios=k, jenis_pupuk__name='NPK', date__year=current_year).aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        dist_urea = Distribution.objects.filter(kios=k, jenis_pupuk__name='UREA', date__year=current_year).aggregate(Sum('tonnage'))['tonnage__sum'] or 0

        persen_npk = (dist_npk / alloc_npk * 100) if alloc_npk > 0 else 0
        persen_urea = (dist_urea / alloc_urea * 100) if alloc_urea > 0 else 0

        report_data.append({
            'name': k.name,
            'district': k.kecamatan.name, # Ambil dari relation
            'npk': {'target': alloc_npk, 'real': dist_npk, 'persen': persen_npk},
            'urea': {'target': alloc_urea, 'real': dist_urea, 'persen': persen_urea},
        })

    return render(request, 'core/raport_kios.html', {'report': report_data})

@login_required
def armada_list(request):
    armada = Armada.objects.all()
    return render(request, 'core/armada_list.html', {'armada': armada})

@login_required
def armada_create(request):
    if request.method == 'POST':
        form = ArmadaForm(request.POST, request.FILES) # request.FILES for photo
        if form.is_valid():
            form.save()
            messages.success(request, "Armada berhasil ditambahkan.")
            return redirect('armada_list')
    else:
        form = ArmadaForm()
    return render(request, 'core/armada_form.html', {'form': form})

@login_required
def master_harga(request):
    """
    Halaman Setting Harga.
    Logic Baru: Pastikan JenisPupuk ada dulu, baru buat Harga.
    """
    # 1. Pastikan Master Jenis Pupuk tersedia (Init Data)
    pupuk_npk, _ = JenisPupuk.objects.get_or_create(
        name='NPK', defaults={'code': 'NPK', 'color': 'danger'}
    )
    pupuk_urea, _ = JenisPupuk.objects.get_or_create(
        name='UREA', defaults={'code': 'UREA', 'color': 'primary'}
    )

    # 2. Ambil/Buat Data Harga
    harga_npk, _ = FertilizerPrice.objects.get_or_create(
        jenis_pupuk=pupuk_npk, defaults={'price_buy': 2300000, 'price_sell': 2350000}
    )
    harga_urea, _ = FertilizerPrice.objects.get_or_create(
        jenis_pupuk=pupuk_urea, defaults={'price_buy': 2200000, 'price_sell': 2250000}
    )

    if request.method == 'POST':
        form_npk = HargaPupukForm(request.POST, instance=harga_npk, prefix='npk')
        form_urea = HargaPupukForm(request.POST, instance=harga_urea, prefix='urea')
        
        if form_npk.is_valid() and form_urea.is_valid():
            form_npk.save()
            form_urea.save()
            messages.success(request, "Harga Pupuk Berhasil Diupdate!")
            return redirect('master_harga')
    else:
        form_npk = HargaPupukForm(instance=harga_npk, prefix='npk')
        form_urea = HargaPupukForm(instance=harga_urea, prefix='urea')

    return render(request, 'core/master_harga.html', {
        'form_npk': form_npk,
        'form_urea': form_urea
    })

# ==========================================
# VIEW LAPORAN KEUANGAN (THE CORE LOGIC)
# ==========================================
@login_required
def laporan_keuangan(request):
    """
    Laporan Laba Rugi (Profit & Loss Statement).
    Menghitung: Omzet - HPP - Biaya Ops = Laba Bersih.
    """
    
    # 1. SETUP TANGGAL (Default: Awal Bulan s/d Hari Ini)
    today = date.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    default_end = today.strftime('%Y-%m-%d')

    start_date = request.GET.get('start', default_start)
    end_date = request.GET.get('end', default_end)

    # 2. SIAPKAN HARGA ACUAN (Master Price) - gunakan FK langsung
    harga_npk = FertilizerPrice.objects.select_related('jenis_pupuk').filter(jenis_pupuk__code='NPK').first()
    harga_urea = FertilizerPrice.objects.select_related('jenis_pupuk').filter(jenis_pupuk__code='UREA').first()

    # Jika harga tidak ditemukan, lemparkan info agar pengguna mengisi master harga
    if not harga_npk or not harga_urea:
        messages.error(request, "Harga pupuk belum dikonfigurasi. Silakan set di Master Harga.")
        return redirect('master_harga')

    # 3. HITUNG MODAL PENEBUSAN (HPP / COGS)
    # Logic: Total Tonase dari 'SalesOrderAllocation' dalam periode ini
    # Kita menggunakan Allocation karena SO Header tidak menyimpan total tonase secara langsung di DB (hanya property)
    
    # -- NPK --
    qty_beli_npk = SalesOrderAllocation.objects.filter(
        sales_order__date__range=[start_date, end_date], 
        sales_order__jenis_pupuk__name='NPK'
    ).aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    # -- UREA --
    qty_beli_urea = SalesOrderAllocation.objects.filter(
        sales_order__date__range=[start_date, end_date], 
        sales_order__jenis_pupuk__name='UREA'
    ).aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    # Hitung Nilai Rupiah Modal
    modal_npk = qty_beli_npk * harga_npk.price_buy / Decimal('1000')
    modal_urea = qty_beli_urea * harga_urea.price_buy / Decimal('1000')
    total_modal = modal_npk + modal_urea

    # 4. HITUNG OMZET PENJUALAN (REVENUE)
    # Logic: Total Tonase dari 'Distribution' dalam periode ini
    
    # -- NPK --
    qty_jual_npk = Distribution.objects.filter(
        date__range=[start_date, end_date],
        jenis_pupuk__name='NPK'
    ).aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    # -- UREA --
    qty_jual_urea = Distribution.objects.filter(
        date__range=[start_date, end_date],
        jenis_pupuk__name='UREA'
    ).aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    # Hitung Nilai Rupiah Omzet (Menggunakan Harga Jual saat ini)
    # Note: Jika ingin super akurat, harusnya 'Distribution' menyimpan harga saat transaksi (snapshot).
    # Di Phase 1 ini kita gunakan Master Harga Jual.
    omzet_npk = qty_jual_npk * harga_npk.price_sell / Decimal('1000')
    omzet_urea = qty_jual_urea * harga_urea.price_sell / Decimal('1000')
    total_omzet = omzet_npk + omzet_urea

    # 5. HITUNG BIAYA OPERASIONAL
    # Logic: Sum Nominal dari BiayaOperasional group by Kategori Utama
    
    biaya_armada = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        kategori_utama='ARMADA',
        status='SELESAI'
    ).aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    biaya_kantor = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        kategori_utama='KANTOR',
        status='SELESAI'
    ).aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']
    
    # Biaya Lainnya (Opsional)
    biaya_lain = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        kategori_utama='LAINNYA',
        status='SELESAI'
    ).aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    total_ops = biaya_armada + biaya_kantor + biaya_lain

    # 6. KALKULASI PROFIT
    gross_profit = total_omzet - total_modal # Laba Kotor
    net_profit = gross_profit - total_ops    # Laba Bersih

    # 7. VALUASI ASET (SISA STOK REAL-TIME)
    # Menggunakan StockCard sebagai 'Single Source of Truth'
    # Rumus: (Total Masuk - Total Keluar) sampai hari ini
    
    def get_stock_balance(pupuk_name):
        agg = StockCard.objects.filter(
            date__lte=end_date, # Saldo per tanggal akhir laporan
            jenis_pupuk__name=pupuk_name
        ).aggregate(
            masuk=Coalesce(Sum('qty_in'), Decimal('0')),
            keluar=Coalesce(Sum('qty_out'), Decimal('0'))
        )
        return agg['masuk'] - agg['keluar']

    stok_sisa_npk = get_stock_balance('NPK')
    stok_sisa_urea = get_stock_balance('UREA')

    aset_npk = stok_sisa_npk * harga_npk.price_buy / Decimal('1000')
    aset_urea = stok_sisa_urea * harga_urea.price_buy / Decimal('1000')
    total_aset = aset_npk + aset_urea

    # --- BUNGKUS DATA (CONTEXT) ---
    context = {
        # Filter
        'start_date': start_date,
        'end_date': end_date,
        
        # Pendapatan
        'omzet_npk': omzet_npk,
        'omzet_urea': omzet_urea,
        'total_omzet': total_omzet,
        'qty_jual_npk': qty_jual_npk,
        'qty_jual_urea': qty_jual_urea,
        
        # Pengeluaran (HPP)
        'modal_npk': modal_npk,
        'modal_urea': modal_urea,
        'total_modal': total_modal,
        'qty_beli_npk': qty_beli_npk,
        'qty_beli_urea': qty_beli_urea,
        
        # Biaya Ops
        'ops_armada': biaya_armada,
        'ops_kantor': biaya_kantor,
        'ops_lain': biaya_lain,
        'total_ops': total_ops,
        
        # Hasil Akhir
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        
        # Aset
        'aset_npk': aset_npk,
        'aset_urea': aset_urea,
        'total_aset': total_aset,
        'stok_sisa_npk': stok_sisa_npk,
        'stok_sisa_urea': stok_sisa_urea,
    }

    # --- EXPORT EXCEL LOGIC ---
    if request.GET.get('export') == 'xls':
        return export_laporan_xls(start_date, end_date, context)

    return render(request, 'core/laporan_keuangan.html', context)

# --- FUNGSI BANTUAN: EXPORT EXCEL (Tetap sama, sesuaikan field jika perlu) ---
def export_laporan_xls(start, end, data):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Laporan_Keuangan_{start}_{end}.csv"'
    writer = csv.writer(response)
    # (Isi CSV bisa disesuaikan dengan data context di atas)
    writer.writerow(['LAPORAN KEUANGAN SIM BADA TANI'])
    writer.writerow([f'Periode: {start} s/d {end}'])
    writer.writerow(['LABA BERSIH', data['net_profit']])
    return response