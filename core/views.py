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
from django.db.models import Sum, Prefetch, F, DecimalField, ProtectedError
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
from .utils import scope_by_kabupaten, get_scope_kabupaten, get_price_for
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
    kab = get_scope_kabupaten(request)
    if kab and kios.kecamatan.kabupaten != kab:
        messages.error(request, "Akses ditolak untuk kabupaten lain.")
        return redirect('kios_list')
    if request.method == 'POST':
        try:
            kios.delete()
            messages.success(request, "Kios berhasil dihapus.")
        except ProtectedError:
            messages.error(
                request,
                "Kios tidak bisa dihapus karena masih memiliki data distribusi, "
                "alokasi, atau transaksi terkait. Nonaktifkan kios sebagai gantinya."
            )
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
    
    # 1. HITUNG UANG (scoped by kabupaten)
    piutang_qs = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL'])
    if kab:
        piutang_qs = piutang_qs.filter(distribution__kios__kecamatan__kabupaten=kab)
    piutang_data = piutang_qs.aggregate(
        total_sisa=Sum(
            F('total_amount') - F('total_paid'), 
            output_field=DecimalField()
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
    overdue_qs = Invoice.objects.filter(
        status__in=['UNPAID', 'PARTIAL'], 
        due_date__lte=today
    )
    if kab:
        overdue_qs = overdue_qs.filter(distribution__kios__kecamatan__kabupaten=kab)
    invoice_overdue_count = overdue_qs.count()

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
    Superuser bisa filter per kabupaten via dropdown.
    """
    current_year = date.today().year

    # Kabupaten filter (superuser only)
    kab_options = Kabupaten.objects.filter(is_active=True).order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    selected_kab_id = request.GET.get('kabupaten', '')
    selected_kab = None

    kios_data = Kios.objects.filter(is_active=True).prefetch_related('allocations', 'kecamatan__kabupaten')

    if request.user.is_superuser:
        if selected_kab_id:
            selected_kab = Kabupaten.objects.filter(pk=selected_kab_id, is_active=True).first()
            if selected_kab:
                kios_data = kios_data.filter(kecamatan__kabupaten=selected_kab)
        # Jika tidak ada filter, tampilkan semua (default superuser)
    else:
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
        'kab_options': kab_options,
        'selected_kabupaten': selected_kab.id if selected_kab else '',
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
@user_passes_test(lambda u: u.is_staff)
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
    Laporan Laba Rugi & Posisi Keuangan (Profit & Loss + Balance Snapshot).

    Prinsip akuntansi yang diterapkan:
    ─────────────────────────────────
    1. Revenue Recognition — Omzet dihitung dari harga terkunci (price snapshot)
       saat surat jalan dibuat, bukan harga master saat laporan dilihat.
    2. Matching Principle — HPP menggunakan sumber yang sama (price snapshot)
       sehingga Omzet detail & total selalu konsisten.
    3. Historical Cost — Persediaan dinilai berdasar harga beli master saat ini
       (approx. weighted-average) karena stok tidak mencatat harga perolehan
       per transaksi masuk.
    4. Piutang Historis — Saldo piutang dihitung per tanggal akhir laporan
       (bukan status terkini) agar laporan masa lalu tetap akurat.
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
            'produk_data': [],
            'net_profit': zero,
            'gross_margin_pct': zero,
            'net_margin_pct': zero,
            'opex_ratio_pct': zero,
            'total_ops': zero,
            'gross_profit': zero,
            'total_omzet': zero,
            'total_modal': zero,
            'ops_armada': zero,
            'ops_kantor': zero,
            'ops_lain': zero,
            'cash_estimate': zero,
            'total_piutang': zero,
            'assets_total': zero,
            'total_aset': zero,
            'liabilities_total': zero,
            'equity_total': zero,
            'liab_equity_total': zero,
            'balance_gap': zero,
            'is_balanced': True,
            'stok_is_global': False,
        }

    # 2. VALIDASI KABUPATEN
    if not kab:
        messages.error(request, "Pilih kabupaten terlebih dahulu untuk melihat laporan.")
        return render(request, 'core/laporan_keuangan.html', empty_context())

    # 3. SIAPKAN HARGA ACUAN (Master Price) — untuk fallback & valuasi stok
    active_types = JenisPupuk.objects.filter(is_active=True).order_by('name')
    prices = {}  # {jp.id: FertilizerPrice}
    for jp in active_types:
        p = get_price_for(jp, kab)
        if not p or p.price_buy <= 0 or p.price_sell <= 0:
            messages.error(request, f"Harga {jp.name} belum dikonfigurasi atau masih 0 untuk kabupaten ini. Silakan set di Master Harga.")
            return render(request, 'core/laporan_keuangan.html', empty_context())
        prices[jp.id] = p

    if not active_types.exists():
        messages.error(request, "Belum ada jenis pupuk aktif. Tambahkan di Master Data Pupuk.")
        return render(request, 'core/laporan_keuangan.html', empty_context())

    # ═══════════════════════════════════════════════════════
    # 4. HITUNG OMZET & HPP PER PRODUK (Sumber Konsisten)
    # ═══════════════════════════════════════════════════════
    # Menggunakan DistributionItem dengan price snapshot yang terkunci
    # saat surat jalan dibuat. Jika snapshot belum terisi (data lama),
    # fallback ke harga master saat ini.
    dist_qs = DistributionItem.objects.select_related(
        'distribution__kios__kecamatan__kabupaten', 'jenis_pupuk'
    ).filter(
        distribution__date__range=[start_date, end_date],
    )
    if kab:
        dist_qs = dist_qs.filter(distribution__kios__kecamatan__kabupaten=kab)

    produk_data = []
    total_omzet = Decimal('0')
    total_modal = Decimal('0')

    for jp in active_types:
        price = prices[jp.id]
        items = dist_qs.filter(jenis_pupuk=jp)

        # Hitung omzet & HPP per item menggunakan harga snapshot
        qty_jual = Decimal('0')
        omzet = Decimal('0')
        modal = Decimal('0')
        for item in items:
            ton = item.tonnage or Decimal('0')
            # Gunakan harga terkunci; fallback ke master price
            sell_price = item.price_sell_snapshot if item.price_sell_snapshot is not None else price.price_sell
            buy_price = item.price_buy_snapshot if item.price_buy_snapshot is not None else price.price_buy
            qty_jual += ton
            omzet += ton * sell_price
            modal += ton * buy_price

        gp = omzet - modal
        avg_sell = omzet / qty_jual if qty_jual else Decimal('0')
        avg_cost = modal / qty_jual if qty_jual else Decimal('0')

        # Valuasi stok fisik (gudang penyangga — shared, bukan per kabupaten)
        agg_stok = StockCard.objects.filter(
            date__lte=end_date,
            jenis_pupuk=jp,
            stock_type='PHYSICAL'
        ).aggregate(
            masuk=Coalesce(Sum('qty_in'), Decimal('0')),
            keluar=Coalesce(Sum('qty_out'), Decimal('0'))
        )
        stok_sisa = agg_stok['masuk'] - agg_stok['keluar']
        # Valuasi persediaan menggunakan harga beli master (approx. weighted-average)
        aset = stok_sisa * price.price_buy

        produk_data.append({
            'name': jp.name,
            'code': jp.code,
            'qty_jual': qty_jual,
            'omzet': omzet,
            'modal': modal,
            'gp': gp,
            'avg_sell': avg_sell,
            'avg_cost': avg_cost,
            'stok_sisa': stok_sisa,
            'aset': aset,
        })
        total_omzet += omzet
        total_modal += modal

    total_aset = sum(p['aset'] for p in produk_data)

    # ═══════════════════════════════════════════════════════
    # 5. HITUNG BIAYA OPERASIONAL
    # ═══════════════════════════════════════════════════════
    biaya_qs = BiayaOperasional.objects.filter(
        tanggal__range=[start_date, end_date],
        status='SELESAI'
    ).select_related('kabupaten')
    if kab:
        biaya_qs = biaya_qs.filter(kabupaten=kab)

    biaya_armada = biaya_qs.filter(kategori_utama='ARMADA').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']
    biaya_kantor = biaya_qs.filter(kategori_utama='KANTOR').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']
    biaya_lain = biaya_qs.filter(kategori_utama='LAINNYA').aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    # ═══════════════════════════════════════════════════════
    # 6. HITUNG TOTAL, LABA, MARGIN
    # ═══════════════════════════════════════════════════════
    total_ops = biaya_armada + biaya_kantor + biaya_lain
    gross_profit = total_omzet - total_modal
    net_profit = gross_profit - total_ops
    gross_margin_pct = (gross_profit / total_omzet * 100) if total_omzet else Decimal('0')
    net_margin_pct = (net_profit / total_omzet * 100) if total_omzet else Decimal('0')
    opex_ratio_pct = (total_ops / total_omzet * 100) if total_omzet else Decimal('0')

    # ═══════════════════════════════════════════════════════
    # 7. SNAPSHOT PIUTANG HISTORIS
    # ═══════════════════════════════════════════════════════
    # Piutang = total tagihan invoice s/d end_date DIKURANGI total pembayaran
    # APPROVED s/d end_date. Ini memberikan snapshot akurat per tanggal laporan,
    # bukan status terkini.
    inv_piutang_qs = Invoice.objects.filter(
        issue_date__lte=end_date
    ).select_related('distribution__kios__kecamatan__kabupaten')
    if kab:
        inv_piutang_qs = inv_piutang_qs.filter(distribution__kios__kecamatan__kabupaten=kab)

    total_tagihan_all = inv_piutang_qs.aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0'))
    )['total']

    # Total pembayaran APPROVED s/d end_date untuk invoice-invoice di atas
    total_bayar_all = Payment.objects.filter(
        status='APPROVED',
        date__lte=end_date,
        invoice__in=inv_piutang_qs
    ).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0'))
    )['total']

    total_piutang = max(Decimal('0'), total_tagihan_all - total_bayar_all)

    # ═══════════════════════════════════════════════════════
    # 8. KAS MASUK PERIODE (Arus Kas Operasional)
    # ═══════════════════════════════════════════════════════
    # Kas = pembayaran masuk APPROVED dalam periode - opex SELESAI dalam periode
    # Ini adalah ARUS KAS BERSIH periode, bukan saldo kas riil.
    pay_qs = Payment.objects.filter(
        status='APPROVED',
        date__range=[start_date, end_date]
    ).select_related('invoice__distribution__kios__kecamatan__kabupaten')
    if kab:
        pay_qs = pay_qs.filter(invoice__distribution__kios__kecamatan__kabupaten=kab)
    payment_total = pay_qs.aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    cash_estimate = payment_total - total_ops

    # ═══════════════════════════════════════════════════════
    # 9. POSISI KEUANGAN (Ringkasan Aset & Kewajiban)
    # ═══════════════════════════════════════════════════════
    # Catatan: Ini BUKAN neraca akuntansi lengkap karena:
    # - Tidak ada pencatatan modal awal / ekuitas pemilik
    # - Liabilitas hanya mencakup biaya ops yang belum di-approve
    # - Kas adalah estimasi arus kas, bukan saldo bank riil
    # Namun tetap berguna sebagai snapshot posisi keuangan operasional.

    # Liabilitas = biaya operasional yang masih pending (belum disetujui)
    pending_ops_qs = BiayaOperasional.objects.filter(
        status='PROSES',
        tanggal__lte=end_date
    ).select_related('kabupaten')
    if kab:
        pending_ops_qs = pending_ops_qs.filter(kabupaten=kab)
    liabilities_total = pending_ops_qs.aggregate(total=Coalesce(Sum('nominal'), Decimal('0')))['total']

    # Total Aset Terukur = Piutang + Persediaan
    # (Kas tidak dimasukkan karena hanya estimasi arus kas, bukan saldo riil)
    assets_total = total_piutang + total_aset

    # Equity dihitung sebagai residual — TIDAK digunakan untuk "balance check"
    # karena tanpa modal awal dan saldo kas riil, neraca tidak bisa seimbang.
    equity_total = assets_total - liabilities_total
    liab_equity_total = liabilities_total + equity_total

    # ═══════════════════════════════════════════════════════
    # Deteksi apakah stok bersifat global (tidak per-kabupaten)
    # ═══════════════════════════════════════════════════════
    stok_is_global = True  # StockCard tidak punya relasi kabupaten

    # --- BUNGKUS DATA (CONTEXT) ---
    context = {
        # Filter
        'start_date': start_date,
        'end_date': end_date,

        # Per-Produk (dinamis)
        'produk_data': produk_data,

        # Pendapatan & HPP aggregat
        'total_omzet': total_omzet,
        'total_modal': total_modal,

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

        # Aset
        'total_aset': total_aset,

        # Balance Snapshot
        'cash_estimate': cash_estimate,
        'payment_total': payment_total,
        'total_piutang': total_piutang,
        'assets_total': assets_total,
        'liabilities_total': liabilities_total,
        'equity_total': equity_total,
        'liab_equity_total': liab_equity_total,
        'stok_is_global': stok_is_global,
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
    """Setup pages restricted to superuser only — admin kabupaten must NOT access."""
    return request.user.is_authenticated and request.user.is_superuser


def setup_forbidden(request):
    messages.error(request, "Anda tidak memiliki akses ke menu Setup. Hanya Superadmin.")
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
    # Cek semua relasi PROTECT sebelum hapus
    refs = []
    if kab.kecamatan_list.exists():
        refs.append('kecamatan')
    if kab.fertilizer_prices.exists():
        refs.append('harga pupuk')
    if kab.users.exists():
        refs.append('user profile')
    if kab.ops_list.exists():
        refs.append('biaya operasional')
    if refs:
        messages.error(request, f"Tidak bisa hapus: kabupaten masih dipakai di data {', '.join(refs)}.")
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
    # Cek semua relasi PROTECT sebelum hapus
    from gudang.models import SalesOrderAllocation, OrderNote
    refs = []
    if kec.kios_list.exists():
        refs.append('kios')
    if SalesOrderAllocation.objects.filter(kecamatan=kec).exists():
        refs.append('alokasi SO')
    if OrderNote.objects.filter(kecamatan=kec).exists():
        refs.append('catatan order')
    if refs:
        messages.error(request, f"Tidak bisa hapus: kecamatan masih dipakai di data {', '.join(refs)}.")
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
    users = User.objects.filter(is_superuser=False).select_related('profile__kabupaten').prefetch_related('groups').order_by('username')
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
def setup_user_edit(request, user_id):
    if not _staff_required(request):
        return setup_forbidden(request)

    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)
    from .forms import UserEditForm
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{target_user.username}' berhasil diperbarui.")
            return redirect('setup_users')
        messages.error(request, "Periksa kembali input Anda.")
    else:
        profile = getattr(target_user, 'profile', None)
        group = target_user.groups.first()
        initial = {
            'kabupaten': profile.kabupaten if profile else None,
            'role': 'admin' if group and group.name == 'Admin' else 'staff',
        }
        form = UserEditForm(instance=target_user, initial=initial)

    return render(request, 'setup/user_edit.html', {'form': form, 'target_user': target_user})


@login_required
@require_http_methods(["POST"])
def setup_user_delete(request, user_id):
    if not _staff_required(request):
        return setup_forbidden(request)

    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)
    # Jangan izinkan hapus diri sendiri
    if target_user == request.user:
        messages.error(request, "Tidak bisa menghapus akun Anda sendiri.")
        return redirect('setup_users')
    username = target_user.username
    target_user.delete()
    messages.success(request, f"User '{username}' berhasil dihapus.")
    return redirect('setup_users')


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
    response.write('\ufeff')  # BOM agar Excel baca UTF-8 dengan benar
    writer = csv.writer(response)

    writer.writerow(['LAPORAN KEUANGAN SIM BADA TANI'])
    writer.writerow([f'Periode: {start} s/d {end}'])
    writer.writerow([])

    # === LABA RUGI ===
    writer.writerow(['LABA RUGI'])
    writer.writerow(['Komponen', 'Nilai (Rp)'])
    for p in data.get('produk_data', []):
        writer.writerow([f'Penjualan {p["name"]}', p['omzet']])
    writer.writerow(['TOTAL OMZET', data['total_omzet']])
    writer.writerow([])
    for p in data.get('produk_data', []):
        writer.writerow([f'HPP {p["name"]}', p['modal']])
    writer.writerow(['TOTAL HPP', data['total_modal']])
    writer.writerow([])
    writer.writerow(['LABA KOTOR', data['gross_profit']])
    writer.writerow(['Gross Margin (%)', data['gross_margin_pct']])
    writer.writerow([])

    # === BIAYA OPERASIONAL ===
    writer.writerow(['BIAYA OPERASIONAL'])
    writer.writerow(['Biaya Armada', data['ops_armada']])
    writer.writerow(['Biaya Kantor', data['ops_kantor']])
    writer.writerow(['Biaya Lainnya', data['ops_lain']])
    writer.writerow(['TOTAL OPEX', data['total_ops']])
    writer.writerow(['Opex Ratio (%)', data['opex_ratio_pct']])
    writer.writerow([])

    # === HASIL AKHIR ===
    writer.writerow(['LABA BERSIH', data['net_profit']])
    writer.writerow(['Net Margin (%)', data['net_margin_pct']])
    writer.writerow([])

    # === PER PRODUK ===
    writer.writerow(['DETAIL PER PRODUK'])
    writer.writerow(['Produk', 'Qty Jual (Ton)', 'Omzet', 'HPP', 'Gross Profit', 'Avg Sell/Ton', 'Avg Cost/Ton', 'Sisa Stok (Ton)', 'Nilai Persediaan'])
    for p in data.get('produk_data', []):
        writer.writerow([
            p['name'], p['qty_jual'], p['omzet'], p['modal'], p['gp'],
            p['avg_sell'], p['avg_cost'], p['stok_sisa'], p['aset']
        ])
    writer.writerow([])

    # === POSISI KEUANGAN ===
    writer.writerow(['POSISI KEUANGAN'])
    writer.writerow(['Piutang Usaha', data['total_piutang']])
    writer.writerow(['Persediaan (Gudang)', data['total_aset']])
    writer.writerow(['Total Aset Terukur', data['assets_total']])
    writer.writerow([])
    writer.writerow(['Arus Kas Bersih Periode', data['cash_estimate']])
    writer.writerow(['Liabilitas (Ops Pending)', data['liabilities_total']])

    return response