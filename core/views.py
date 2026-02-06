from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.forms import modelformset_factory
from django.db.models import Sum, Prefetch, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date
import csv
from django.http import HttpResponse

# Import Models Baru
from .models import Kios, Armada, FertilizerPrice, JenisPupuk, Kecamatan, KiosAllocation, CompanyProfile, Kabupaten, UserProfile
from .forms import (
    KiosForm,
    KiosAllocationFormSet,
    ArmadaForm,
    HargaPupukForm,
    JenisPupukForm,
    CompanyProfileForm,
    KecamatanForm,
    KabupatenForm,
    UserCreateForm,
    UserSetPasswordForm,
)
from .utils import scope_by_kabupaten, get_scope_kabupaten, get_price_by_code
User = get_user_model()

from gudang.models import SalesOrder, SalesOrderAllocation, Distribution, DistributionItem, StockCard
from keuangan.models import Invoice, BiayaOperasional, Payment

# 1. READ (Daftar Kios)
@login_required
def kios_list(request):
    # Select related kecamatan agar query efisien
    current_year = date.today().year
    alloc_qs = KiosAllocation.objects.filter(year=current_year).select_related('jenis_pupuk')
    kios_data = (
        Kios.objects.select_related('kecamatan__kabupaten')
        .prefetch_related(Prefetch('allocations', queryset=alloc_qs))
        .order_by('-created_at')
    )
    kios_data = scope_by_kabupaten(kios_data, request.user, 'kecamatan__kabupaten')

    # Hitung realisasi distribusi per kios x jenis pupuk di tahun berjalan
    kios_ids = [k.id for k in kios_data]
    dist_map = {}
    if kios_ids:
        dist_agg = DistributionItem.objects.filter(
            distribution__kios_id__in=kios_ids,
            distribution__date__year=current_year
        ).values('distribution__kios_id', 'jenis_pupuk_id').annotate(total=Sum('tonnage'))

        for row in dist_agg:
            dist_map[(row['distribution__kios_id'], row['jenis_pupuk_id'])] = row['total'] or Decimal('0')

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

        kab = get_scope_kabupaten(request)
        if kab:
            form.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten=kab)
            for alloc_form in formset.forms:
                alloc_form.fields['jenis_pupuk'].queryset = alloc_form.fields['jenis_pupuk'].queryset
        
        
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

    kab = get_scope_kabupaten(request)
    if kab:
        form.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten=kab)
        for alloc_form in formset.forms:
            alloc_form.fields['jenis_pupuk'].queryset = alloc_form.fields['jenis_pupuk'].queryset

    return render(request, 'core/kios_form.html', {
        'form': form, 
        'formset': formset, 
        'title': 'Tambah Kios Baru'
    })

# 3. UPDATE (Edit Kios)
@login_required
def kios_update(request, pk):
    kios = get_object_or_404(Kios, pk=pk)
    kab = get_scope_kabupaten(request)
    if kab and kios.kecamatan.kabupaten != kab:
        messages.error(request, "Akses ditolak untuk kabupaten lain.")
        return redirect('kios_list')
    
    if request.method == 'POST':
        form = KiosForm(request.POST, instance=kios)
        formset = KiosAllocationFormSet(request.POST, instance=kios)

        if kab:
            form.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten=kab)
        
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

    if kab:
        form.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten=kab)

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
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    
    # 1. HITUNG UANG (FIXED: Tambahkan output_field)
    piutang_data = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(
        total_sisa=Sum(
            F('total_amount') - F('total_paid'), 
            output_field=DecimalField() # <--- WAJIB ADA
        )
    )
    total_piutang = piutang_data['total_sisa'] or 0

    # 2. HITUNG STOK TERPISAH (FIXED: Tambahkan output_field pada Coalesce)
    def get_stock_balance(jenis_pupuk, tipe_stok):
        qs = StockCard.objects.filter(
            jenis_pupuk=jenis_pupuk,
            stock_type=tipe_stok
        )
        val = qs.aggregate(
            saldo=Coalesce(Sum('qty_in'), 0, output_field=DecimalField()) - 
                  Coalesce(Sum('qty_out'), 0, output_field=DecimalField())
        )['saldo']
        
        return val if val is not None else 0

    # Ambil semua jenis pupuk aktif untuk stok dinamis
    jenis_aktif = JenisPupuk.objects.filter(is_active=True).order_by('name')
    stok_virtual = []
    stok_fisik = []
    for jp in jenis_aktif:
        stok_virtual.append({'jenis': jp, 'saldo': get_stock_balance(jp, 'VIRTUAL')})
        stok_fisik.append({'jenis': jp, 'saldo': get_stock_balance(jp, 'PHYSICAL')})

    # 3. DATA LAINNYA
    invoice_overdue_count = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL'], 
        due_date__lte=today
    ).count()

    invoices_qs = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']) \
                                    .select_related('distribution__kios__kecamatan__kabupaten')
    if kab:
        invoices_qs = invoices_qs.filter(distribution__kios__kecamatan__kabupaten=kab)
    invoices_list = invoices_qs.order_by('due_date')[:5]

    so_qs = SalesOrder.objects.filter(is_closed=False).prefetch_related('allocations__kecamatan__kabupaten')
    if kab:
        so_qs = so_qs.filter(allocations__kecamatan__kabupaten=kab)
    so_expiring = so_qs.order_by('date').distinct()[:5]

    context = {
        'total_piutang': total_piutang,
        'invoice_overdue_count': invoice_overdue_count,
        
        # Stok dinamis per jenis pupuk
        'stok_virtual': stok_virtual,
        'stok_fisik': stok_fisik,
        
        'invoices_list': invoices_list,
        'so_expiring': so_expiring,
        'today': today,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    }

    return render(request, 'dashboard.html', context)


@login_required
def raport_kios(request):
    """
    Laporan Kinerja Kios: Alokasi vs Realisasi.
    Dinamis — semua jenis pupuk aktif ditampilkan.
    """
    current_year = date.today().year
    kios_data = Kios.objects.filter(is_active=True).prefetch_related('allocations', 'kecamatan__kabupaten')
    kios_data = scope_by_kabupaten(kios_data, request.user, 'kecamatan__kabupaten')

    jenis_list = list(JenisPupuk.objects.filter(is_active=True).order_by('name'))
    report_data = []

    for k in kios_data:
        pupuk_data = []
        for jp in jenis_list:
            alloc_val = k.allocations.filter(jenis_pupuk=jp, year=current_year).aggregate(
                Sum('quota_original'))['quota_original__sum'] or 0
            dist_val = DistributionItem.objects.filter(
                distribution__kios=k,
                jenis_pupuk=jp,
                distribution__date__year=current_year
            ).aggregate(total=Sum('tonnage'))['total'] or 0
            persen = (dist_val / alloc_val * 100) if alloc_val > 0 else 0
            pupuk_data.append({
                'jenis': jp,
                'target': alloc_val,
                'real': dist_val,
                'persen': persen,
            })
        report_data.append({
            'name': k.name,
            'district': k.kecamatan.name,
            'pupuk': pupuk_data,
        })

    return render(request, 'core/raport_kios.html', {
        'report': report_data,
        'jenis_list': jenis_list,
        'current_year': current_year,
    })

@login_required
def armada_list(request):
    armada = Armada.objects.all()
    return render(request, 'core/armada_list.html', {'armada': armada})

@login_required
def armada_create(request):
    if request.method == 'POST':
        form = ArmadaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Armada berhasil ditambahkan.")
            return redirect('armada_list')
    else:
        form = ArmadaForm()
    return render(request, 'core/armada_form.html', {'form': form, 'title': 'Tambah Armada Baru'})

@login_required
def armada_update(request, pk):
    armada = get_object_or_404(Armada, pk=pk)
    if request.method == 'POST':
        form = ArmadaForm(request.POST, request.FILES, instance=armada)
        if form.is_valid():
            form.save()
            messages.success(request, "Data armada berhasil diperbarui.")
            return redirect('armada_list')
    else:
        form = ArmadaForm(instance=armada)
    return render(request, 'core/armada_form.html', {'form': form, 'title': f'Edit Armada: {armada.plate_number}'})

@login_required
def armada_delete(request, pk):
    armada = get_object_or_404(Armada, pk=pk)
    if request.method == 'POST':
        # Cek apakah armada masih dipakai di distribusi
        if Distribution.objects.filter(armada=armada).exists():
            # Soft-delete: nonaktifkan saja
            armada.is_active = False
            armada.save(update_fields=['is_active'])
            messages.warning(request, f"Armada {armada.plate_number} masih dipakai di distribusi, status dinonaktifkan.")
        else:
            armada.delete()
            messages.success(request, "Armada berhasil dihapus.")
        return redirect('armada_list')
    return render(request, 'core/armada_confirm_delete.html', {'armada': armada})

@login_required
def master_harga(request):
    return redirect('master_data_pupuk')


@login_required
@user_passes_test(lambda u: u.is_staff)
def master_data_pupuk(request):
    """Satu halaman untuk jenis pupuk + harga."""
    PriceFormSet = modelformset_factory(FertilizerPrice, form=HargaPupukForm, extra=0)

    show_archived = request.GET.get('archived') == '1'

    pupuk_list = list(JenisPupuk.objects.filter(is_active=True).order_by('name'))
    archived_pupuk = list(JenisPupuk.objects.filter(is_active=False).order_by('name')) if show_archived else []

    # Tentukan kabupaten kerja
    kab_scope = get_scope_kabupaten(request)
    if request.user.is_superuser and not kab_scope:
        post_kab_id = request.POST.get('kabupaten')
        if post_kab_id:
            kab_scope = Kabupaten.objects.filter(pk=post_kab_id, is_active=True).first()
    kab_options = Kabupaten.objects.filter(is_active=True).order_by('name') if request.user.is_superuser else Kabupaten.objects.none()

    # Superuser wajib pilih kabupaten untuk mengelola harga
    if request.user.is_superuser and not kab_scope:
        messages.error(request, "Pilih kabupaten dulu untuk mengelola harga.")
        price_qs = FertilizerPrice.objects.none()
        price_formset = PriceFormSet(queryset=price_qs, prefix='prices')
        jenis_form = JenisPupukForm(prefix='jenis', instance=None)
        return render(request, 'core/master_data_pupuk.html', {
            'jenis_form': jenis_form,
            'price_formset': price_formset,
            'price_items': [],
            'pupuk_list': pupuk_list,
            'edit_target': None,
            'show_archived': show_archived,
            'archived_pupuk': archived_pupuk,
            'kab_options': kab_options,
            'selected_kabupaten': '',
        })

    # Pastikan tiap jenis punya harga untuk kabupaten terpilih
    for jp in pupuk_list:
        FertilizerPrice.objects.get_or_create(
            jenis_pupuk=jp,
            kabupaten=kab_scope,
            defaults={'price_buy': Decimal('0'), 'price_sell': Decimal('0')}
        )

    price_qs = FertilizerPrice.objects.filter(jenis_pupuk__in=pupuk_list, kabupaten=kab_scope)
    price_qs = price_qs.select_related('jenis_pupuk', 'kabupaten').order_by('jenis_pupuk__name')

    action = request.POST.get('action') if request.method == 'POST' else None

    edit_id = request.GET.get('edit')
    edit_target = None
    if edit_id:
        edit_target = get_object_or_404(JenisPupuk, pk=edit_id)

    if action == 'update_prices':
        price_formset = PriceFormSet(request.POST, queryset=price_qs, prefix='prices')
        jenis_form = JenisPupukForm(prefix='jenis', instance=edit_target)
        if price_formset.is_valid():
            price_formset.save()
            messages.success(request, "Harga pupuk berhasil diperbarui.")
            return redirect('master_data_pupuk')
        messages.error(request, "Periksa input harga yang bertanda merah.")

    elif action == 'create_jenis':
        jenis_form = JenisPupukForm(request.POST, prefix='jenis')
        price_formset = PriceFormSet(queryset=price_qs, prefix='prices')
        if jenis_form.is_valid():
            jenis = jenis_form.save()
            FertilizerPrice.objects.get_or_create(
                jenis_pupuk=jenis,
                kabupaten=kab_scope,
                defaults={'price_buy': Decimal('0'), 'price_sell': Decimal('0')}
            )
            messages.success(request, "Jenis pupuk berhasil ditambahkan.")
            return redirect('master_data_pupuk')
        messages.error(request, "Periksa input jenis pupuk yang bertanda merah.")

    elif action == 'update_jenis':
        jenis_id = request.POST.get('jenis_id')
        target = get_object_or_404(JenisPupuk, pk=jenis_id)
        jenis_form = JenisPupukForm(request.POST, prefix='jenis', instance=target)
        price_formset = PriceFormSet(queryset=price_qs, prefix='prices')
        if jenis_form.is_valid():
            jenis_form.save()
            messages.success(request, "Jenis pupuk diperbarui.")
            return redirect('master_data_pupuk')
        messages.error(request, "Periksa input jenis pupuk yang bertanda merah.")

    elif action == 'archive_jenis':
        jenis_id = request.POST.get('jenis_id')
        target = get_object_or_404(JenisPupuk, pk=jenis_id)
        target.is_active = False
        target.save(update_fields=['is_active'])
        messages.warning(request, f"{target.name} diarsipkan.")
        return redirect('master_data_pupuk')

    elif action == 'delete_jenis':
        jenis_id = request.POST.get('jenis_id')
        target = get_object_or_404(JenisPupuk, pk=jenis_id)

        has_refs = (
            KiosAllocation.objects.filter(jenis_pupuk=target).exists() or
            DistributionItem.objects.filter(jenis_pupuk=target).exists() or
            SalesOrder.objects.filter(jenis_pupuk=target).exists() or
            StockCard.objects.filter(jenis_pupuk=target).exists()
        )

        if has_refs:
            target.is_active = False
            target.save(update_fields=['is_active'])
            messages.warning(request, f"{target.name} masih dipakai, status diarsipkan.")
        else:
            FertilizerPrice.objects.filter(jenis_pupuk=target).delete()
            target.delete()
            messages.success(request, f"{target.name} dihapus.")
        return redirect('master_data_pupuk')

    elif action == 'restore_jenis':
        jenis_id = request.POST.get('jenis_id')
        target = get_object_or_404(JenisPupuk, pk=jenis_id)
        target.is_active = True
        target.save(update_fields=['is_active'])
        messages.success(request, f"{target.name} diaktifkan kembali.")
        return redirect('master_data_pupuk')

    else:
        price_formset = PriceFormSet(queryset=price_qs, prefix='prices')
        jenis_form = JenisPupukForm(prefix='jenis', instance=edit_target)

    # Set kabupaten tetap untuk setiap form dalam formset
    for form in price_formset.forms:
        form.fields['kabupaten'].initial = kab_scope
        form.fields['kabupaten'].widget.attrs['value'] = kab_scope.id if kab_scope else ''

    price_items = [
        {'form': form, 'jenis': form.instance.jenis_pupuk}
        for form in price_formset.forms
    ]

    return render(request, 'core/master_data_pupuk.html', {
        'jenis_form': jenis_form,
        'price_formset': price_formset,
        'price_items': price_items,
        'pupuk_list': pupuk_list,
        'edit_target': edit_target,
        'show_archived': show_archived,
        'archived_pupuk': archived_pupuk,
        'kab_options': kab_options,
        'selected_kabupaten': kab_scope.id if kab_scope else '',
    })


# ==========================================
# MASTER JENIS PUPUK (CRUD)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_staff)
def jenis_pupuk_list(request):
    return redirect('master_data_pupuk')


@login_required
@user_passes_test(lambda u: u.is_staff)
def jenis_pupuk_edit(request, pk):
    return redirect(f"{reverse('master_data_pupuk')}?edit={pk}")


@login_required
def jenis_pupuk_delete(request, pk):
    jenis = get_object_or_404(JenisPupuk, pk=pk)
    if request.method != 'POST':
        messages.error(request, "Gunakan tombol hapus untuk mengarsipkan jenis pupuk.")
        return redirect('jenis_pupuk_list')

    # Cek referensi transaksional; jika terpakai, set inactive saja
    # FertilizerPrice tidak dihitung sebagai referensi karena itu master data pendukung
    has_refs = (
        KiosAllocation.objects.filter(jenis_pupuk=jenis).exists() or
        DistributionItem.objects.filter(jenis_pupuk=jenis).exists() or
        SalesOrder.objects.filter(jenis_pupuk=jenis).exists() or
        StockCard.objects.filter(jenis_pupuk=jenis).exists()
    )

    if has_refs:
        jenis.is_active = False
        jenis.save(update_fields=['is_active'])
        messages.warning(request, "Jenis pupuk sudah dipakai; status di-nonaktifkan.")
    else:
        FertilizerPrice.objects.filter(jenis_pupuk=jenis).delete()
        jenis.delete()
        messages.success(request, "Jenis pupuk dihapus.")

    return redirect('jenis_pupuk_list')

# ==========================================
# VIEW LAPORAN KEUANGAN (THE CORE LOGIC)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_staff)
def laporan_keuangan(request):
    """
    Laporan Laba Rugi (Profit & Loss Statement).
    Menghitung: Omzet - HPP - Biaya Ops = Laba Bersih.
    """
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    # Superuser boleh override kabupaten via filter form
    kab_param = request.GET.get('kabupaten')
    if request.user.is_superuser and kab_param:
        kab = kab_options.filter(pk=kab_param).first()
    
    # 1. SETUP TANGGAL (Default: Awal Bulan s/d Hari Ini)
    today = date.today()
    default_start = today.replace(day=1).strftime('%Y-%m-%d')
    default_end = today.strftime('%Y-%m-%d')

    start_date = request.GET.get('start', default_start)
    end_date = request.GET.get('end', default_end)

    # Helper context ketika belum pilih kabupaten atau harga belum siap
    def empty_context():
        zero = Decimal('0')
        return {
            'start_date': start_date,
            'end_date': end_date,
            'kab_options': kab_options,
            'selected_kabupaten': kab.id if kab else None,
            'net_profit': zero,
            'gross_margin_pct': zero,
            'net_margin_pct': zero,
            'opex_ratio_pct': zero,
            'total_ops': zero,
            'gross_profit': zero,
            'total_omzet': zero,
            'omzet_npk': zero,
            'omzet_urea': zero,
            'modal_npk': zero,
            'modal_urea': zero,
            'total_modal': zero,
            'qty_jual_npk': zero,
            'qty_jual_urea': zero,
            'gp_npk': zero,
            'gp_urea': zero,
            'avg_sell_npk': zero,
            'avg_sell_urea': zero,
            'avg_cost_npk': zero,
            'avg_cost_urea': zero,
            'ops_armada': zero,
            'ops_kantor': zero,
            'ops_lain': zero,
            'cash_estimate': zero,
            'total_piutang': zero,
            'assets_total': zero,
            'total_aset': zero,
            'stok_sisa_npk': zero,
            'stok_sisa_urea': zero,
            'is_balanced': True,
        }

    # 2. SIAPKAN HARGA ACUAN (Master Price) - gunakan FK langsung + kabupaten
    harga_npk = get_price_by_code('NPK', kab)
    harga_urea = get_price_by_code('UREA', kab)

    # Validasi harga master
    if not kab:
        messages.error(request, "Pilih kabupaten terlebih dahulu untuk melihat laporan.")
        return render(request, 'core/laporan_keuangan.html', empty_context())
    if not harga_npk or not harga_urea:
        messages.error(request, "Harga pupuk belum dikonfigurasi untuk kabupaten ini. Silakan set di Master Harga.")
        return render(request, 'core/laporan_keuangan.html', empty_context())
    if harga_npk.price_buy <= 0 or harga_npk.price_sell <= 0 or harga_urea.price_buy <= 0 or harga_urea.price_sell <= 0:
        messages.error(request, "Harga pupuk harus lebih dari 0. Perbarui di Master Harga.")
        return render(request, 'core/laporan_keuangan.html', empty_context())

    # Harga master disimpan per ton; distribusi tonnage juga dalam ton.
    ton_to_kg = Decimal('1')

    # 3. HITUNG OMZET PENJUALAN (REVENUE) — basis invoice jika ada, fallback ke tonase x harga master
    dist_qs = DistributionItem.objects.select_related('distribution__kios__kecamatan__kabupaten', 'jenis_pupuk').filter(
        distribution__date__range=[start_date, end_date],
    )
    if kab:
        dist_qs = dist_qs.filter(distribution__kios__kecamatan__kabupaten=kab)

    qty_jual_npk = dist_qs.filter(jenis_pupuk__name='NPK').aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    qty_jual_urea = dist_qs.filter(jenis_pupuk__name='UREA').aggregate(total=Coalesce(Sum('tonnage'), Decimal('0')))['total']

    # Per produk (asumsi harga master per KG; konversi ton -> kg)
    omzet_npk = qty_jual_npk * harga_npk.price_sell * ton_to_kg
    omzet_urea = qty_jual_urea * harga_urea.price_sell * ton_to_kg
    total_omzet_distribution = omzet_npk + omzet_urea

    # Total omzet prefer Invoice (lebih akurat nilai tagihan); jika tidak ada invoice periode ini, pakai distribusi
    inv_qs = Invoice.objects.filter(issue_date__range=[start_date, end_date]).select_related('distribution__kios__kecamatan__kabupaten')
    if kab:
        inv_qs = inv_qs.filter(distribution__kios__kecamatan__kabupaten=kab)

    total_omzet_invoice = inv_qs.aggregate(total=Coalesce(Sum('total_amount'), Decimal('0')))['total']

    total_omzet = total_omzet_invoice if total_omzet_invoice else total_omzet_distribution

    # 4. HITUNG MODAL PENEBUSAN (HPP / COGS) — gunakan qty terjual x harga beli master (per KG)
    modal_npk = qty_jual_npk * harga_npk.price_buy * ton_to_kg
    modal_urea = qty_jual_urea * harga_urea.price_buy * ton_to_kg
    total_modal = modal_npk + modal_urea

    # Kompatibilitas context lama (tidak dipakai di template): samakan pembelian dengan qty terjual
    qty_beli_npk = qty_jual_npk
    qty_beli_urea = qty_jual_urea

    # 5. HITUNG BIAYA OPERASIONAL
    # Logic: Sum Nominal dari BiayaOperasional group by Kategori Utama
    biaya_qs = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        status='SELESAI'
    ).select_related('kabupaten')
    if kab:
        biaya_qs = biaya_qs.filter(kabupaten=kab)

    biaya_armada = biaya_qs.filter(kategori_utama='ARMADA').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    biaya_kantor = biaya_qs.filter(kategori_utama='KANTOR').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']
    
    biaya_lain = biaya_qs.filter(kategori_utama='LAINNYA').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    # 6. HITUNG TOTAL, LABA, MARGIN
    total_ops = biaya_armada + biaya_kantor + biaya_lain
    gross_profit = total_omzet - total_modal
    net_profit = gross_profit - total_ops
    gross_margin_pct = (gross_profit / total_omzet * 100) if total_omzet else Decimal('0')
    net_margin_pct = (net_profit / total_omzet * 100) if total_omzet else Decimal('0')
    opex_ratio_pct = (total_ops / total_omzet * 100) if total_omzet else Decimal('0')

    gp_npk = omzet_npk - modal_npk
    gp_urea = omzet_urea - modal_urea

    avg_sell_npk = omzet_npk / qty_jual_npk if qty_jual_npk else Decimal('0')
    avg_sell_urea = omzet_urea / qty_jual_urea if qty_jual_urea else Decimal('0')
    avg_cost_npk = modal_npk / qty_jual_npk if qty_jual_npk else Decimal('0')
    avg_cost_urea = modal_urea / qty_jual_urea if qty_jual_urea else Decimal('0')

    # 7. VALUASI ASET (SISA STOK REAL-TIME)
    # Menggunakan StockCard sebagai 'Single Source of Truth'
    # Rumus: (Total Masuk - Total Keluar) sampai hari ini
    
    def get_stock_balance(pupuk_name):
        agg = StockCard.objects.filter(
            date__lte=end_date, # Saldo per tanggal akhir laporan
            jenis_pupuk__name=pupuk_name,
            stock_type='PHYSICAL'  # hanya stok fisik siap kirim
        ).aggregate(
            masuk=Coalesce(Sum('qty_in'), Decimal('0')),
            keluar=Coalesce(Sum('qty_out'), Decimal('0'))
        )
        return agg['masuk'] - agg['keluar']

    stok_sisa_npk = get_stock_balance('NPK')
    stok_sisa_urea = get_stock_balance('UREA')

    aset_npk = stok_sisa_npk * harga_npk.price_buy
    aset_urea = stok_sisa_urea * harga_urea.price_buy
    total_aset = aset_npk + aset_urea

    # 8. SNAPSHOT PIUTANG & KAS (periode laporan)
    piutang_qs = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL'],
        issue_date__lte=end_date
    ).select_related('distribution__kios__kecamatan__kabupaten')
    if kab:
        piutang_qs = piutang_qs.filter(distribution__kios__kecamatan__kabupaten=kab)

    piutang_data = piutang_qs.aggregate(total_sisa=Coalesce(Sum(F('total_amount') - F('total_paid'), output_field=DecimalField()), Decimal('0')))
    total_piutang = piutang_data['total_sisa'] or Decimal('0')

    pay_qs = Payment.objects.filter(
        status='APPROVED',
        date__range=[start_date, end_date]
    ).select_related('invoice__distribution__kios__kecamatan__kabupaten')
    if kab:
        pay_qs = pay_qs.filter(invoice__distribution__kios__kecamatan__kabupaten=kab)
    payment_total = pay_qs.aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    cash_estimate = payment_total - total_ops

    # 9. NERACA SINGKAT (Aset = Liabilitas + Ekuitas)
    pending_ops_qs = BiayaOperasional.objects.filter(
        status='PROSES',
        tanggal__lte=end_date
    ).select_related('kabupaten')
    if kab:
        pending_ops_qs = pending_ops_qs.filter(kabupaten=kab)
    pending_ops = pending_ops_qs.aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    liabilities_total = pending_ops
    assets_total = cash_estimate + total_piutang + total_aset
    equity_total = assets_total - liabilities_total
    liab_equity_total = liabilities_total + equity_total
    balance_gap = assets_total - liab_equity_total
    is_balanced = abs(balance_gap) <= Decimal('0.01')

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
        'gross_margin_pct': gross_margin_pct,
        'net_margin_pct': net_margin_pct,
        'opex_ratio_pct': opex_ratio_pct,
        'gp_npk': gp_npk,
        'gp_urea': gp_urea,
        'avg_sell_npk': avg_sell_npk,
        'avg_sell_urea': avg_sell_urea,
        'avg_cost_npk': avg_cost_npk,
        'avg_cost_urea': avg_cost_urea,
        
        # Aset
        'aset_npk': aset_npk,
        'aset_urea': aset_urea,
        'total_aset': total_aset,
        'stok_sisa_npk': stok_sisa_npk,
        'stok_sisa_urea': stok_sisa_urea,

        # Balance Snapshot
        'cash_estimate': cash_estimate,
        'total_piutang': total_piutang,
        'assets_total': assets_total,
        'liabilities_total': liabilities_total,
        'equity_total': equity_total,
        'liab_equity_total': liab_equity_total,
        'balance_gap': balance_gap,
        'is_balanced': is_balanced,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    }

    # --- EXPORT EXCEL LOGIC ---
    if request.GET.get('export') == 'xls':
        return export_laporan_xls(start_date, end_date, context)

    return render(request, 'core/laporan_keuangan.html', context)


# =========================================================
# SETUP PAGES (Company Profile, Kecamatan, User Management)
# =========================================================

def _staff_required(request):
    return request.user.is_authenticated and request.user.is_staff


def setup_forbidden(request):
    messages.error(request, "Anda tidak memiliki akses ke menu Setup.")
    return redirect('dashboard')


@login_required
@never_cache
def setup_company_profile(request):
    if not _staff_required(request):
        return setup_forbidden(request)

    profile, _ = CompanyProfile.objects.get_or_create(pk=1)
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil perusahaan diperbarui.")
            return redirect('setup_company_profile')
        messages.error(request, "Periksa kembali input Anda.")
    else:
        form = CompanyProfileForm(instance=profile)

    return render(request, 'setup/company_profile.html', {'form': form})


@login_required
@never_cache
def setup_kabupaten(request):
    if not _staff_required(request):
        return setup_forbidden(request)

    kab_list = Kabupaten.objects.all().order_by('name')
    form = KabupatenForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Kabupaten berhasil disimpan.")
            return redirect('setup_kabupaten')
        messages.error(request, "Periksa kembali input Anda.")

    return render(request, 'setup/kabupaten_list.html', {'form': form, 'kabupaten_list': kab_list})


@login_required
@never_cache
def setup_kabupaten_edit(request, pk):
    if not _staff_required(request):
        return setup_forbidden(request)

    kab = get_object_or_404(Kabupaten, pk=pk)
    form = KabupatenForm(request.POST or None, instance=kab)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Kabupaten diperbarui.")
            return redirect('setup_kabupaten')
        messages.error(request, "Periksa kembali input Anda.")
    return render(request, 'setup/kabupaten_form.html', {'form': form, 'obj': kab})


@login_required
@require_http_methods(["POST"])
def setup_kabupaten_delete(request, pk):
    if not _staff_required(request):
        return setup_forbidden(request)

    kab = get_object_or_404(Kabupaten, pk=pk)
    if kab.kecamatan_list.exists():
        messages.error(request, "Tidak bisa hapus: kabupaten masih memiliki kecamatan.")
    else:
        kab.delete()
        messages.success(request, "Kabupaten dihapus.")
    return redirect('setup_kabupaten')


@login_required
@never_cache
def setup_kecamatan(request):
    if not _staff_required(request):
        return setup_forbidden(request)

    kecamatan_list = Kecamatan.objects.all()
    form = KecamatanForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Kecamatan berhasil disimpan.")
            return redirect('setup_kecamatan')
        messages.error(request, "Periksa kembali input Anda.")

    return render(request, 'setup/kecamatan_list.html', {'form': form, 'kecamatan_list': kecamatan_list})


@login_required
@never_cache
def setup_kecamatan_edit(request, pk):
    if not _staff_required(request):
        return setup_forbidden(request)

    kec = get_object_or_404(Kecamatan, pk=pk)
    form = KecamatanForm(request.POST or None, instance=kec)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Kecamatan diperbarui.")
            return redirect('setup_kecamatan')
        messages.error(request, "Periksa kembali input Anda.")
    return render(request, 'setup/kecamatan_form.html', {'form': form, 'obj': kec})


@login_required
@require_http_methods(["POST"])
def setup_kecamatan_delete(request, pk):
    if not _staff_required(request):
        return setup_forbidden(request)

    kec = get_object_or_404(Kecamatan, pk=pk)
    if kec.kios_list.exists():
        messages.error(request, "Tidak bisa hapus: kecamatan sudah dipakai di data kios.")
    else:
        kec.delete()
        messages.success(request, "Kecamatan dihapus.")
    return redirect('setup_kecamatan')


def _ensure_default_groups():
    Group.objects.get_or_create(name='Admin')
    Group.objects.get_or_create(name='Staff')


@login_required
@never_cache
def setup_users(request):
    if not _staff_required(request):
        return setup_forbidden(request)

    _ensure_default_groups()
    users = User.objects.filter(is_superuser=False).order_by('username')
    for usr in users:
        UserProfile.objects.get_or_create(user=usr)
    form = UserCreateForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "User baru dibuat.")
            return redirect('setup_users')
        messages.error(request, "Periksa kembali input Anda.")

    return render(request, 'setup/user_list.html', {'form': form, 'users': users})


@login_required
@never_cache
def setup_user_set_password(request, user_id):
    if not _staff_required(request):
        return setup_forbidden(request)

    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    form = UserSetPasswordForm(user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Password diperbarui.")
            return redirect('setup_users')
        messages.error(request, "Periksa kembali input Anda.")

    return render(request, 'setup/user_set_password.html', {'form': form, 'target_user': user})

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