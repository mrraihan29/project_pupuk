import json
import re
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction, IntegrityError
from django.db.models import Sum, Prefetch
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from xhtml2pdf import pisa

# Import Models & Forms Baru
from .models import SalesOrder, SalesOrderAllocation, Distribution, DistributionItem, WarehouseTransfer, StockCard, OrderNote, OrderNoteItem
from .signals import recompute_stock_balance
from .forms import (
    SalesOrderForm, AllocationFormSet, 
    DistributionForm, DistributionItemFormSet,
    WarehouseTransferForm, 
    StockOpnameForm, OrderNoteForm, OrderNoteItemFormSet
)
from django.core.exceptions import ValidationError
from core.models import CompanyProfile, JenisPupuk, Kios, Kabupaten, KiosAllocation
from core.utils import scope_by_kabupaten, get_scope_kabupaten, get_price_for, get_company_profile

# ==========================================
# 1. MODUL PENEBUSAN (SO)
# ==========================================
@login_required
def so_list(request):
    """
    Daftar Sales Order (Penebusan).
    """
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    # Ambil semua data SO, urutkan dari yang terbaru
    orders = SalesOrder.objects.select_related('jenis_pupuk') \
                            .prefetch_related('allocations__kecamatan__kabupaten') \
                            .order_by('-date')
    if kab:
        orders = orders.filter(allocations__kecamatan__kabupaten=kab).distinct()
    # Tambahkan saldo virtual terkini per SO
    for so in orders:
        so.virtual_balance = so.get_virtual_balance()

    return render(request, 'gudang/so_list.html', {
        'orders': orders,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })

@login_required
def so_create(request):
    """
    Input SO Baru dengan Multi-Kecamatan (Dynamic Formset).
    Menggunakan Atomic Transaction untuk keamanan data.
    """
    kab = get_scope_kabupaten(request)
    if request.method == 'POST':
        form = SalesOrderForm(request.POST, request.FILES)
        formset = AllocationFormSet(request.POST)
        # Batasi kecamatan di formset SEBELUM validasi agar tidak bisa submit kecamatan lain
        if kab:
            for form_alloc in formset.forms:
                form_alloc.fields['kecamatan'].queryset = form_alloc.fields['kecamatan'].queryset.filter(kabupaten=kab)
        
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
        if kab:
            for form_alloc in formset.forms:
                form_alloc.fields['kecamatan'].queryset = form_alloc.fields['kecamatan'].queryset.filter(kabupaten=kab)
    
    return render(request, 'gudang/so_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Input Penebusan (SO)'
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def so_edit(request, pk):
    """Edit SO (superadmin only)."""
    so = get_object_or_404(SalesOrder, pk=pk)
    kab = get_scope_kabupaten(request)

    if request.method == 'POST':
        form = SalesOrderForm(request.POST, request.FILES, instance=so)
        formset = AllocationFormSet(request.POST, instance=so)
        if kab:
            for f in formset.forms:
                f.fields['kecamatan'].queryset = f.fields['kecamatan'].queryset.filter(kabupaten=kab)

        if form.is_valid() and formset.is_valid():
            # Guard: Cegah ganti jenis_pupuk jika SO sudah punya transfer/distribusi
            if form.cleaned_data['jenis_pupuk'] != so.jenis_pupuk:
                has_transfers = so.transfers.exists()
                has_distributions = DistributionItem.objects.filter(source_so=so).exists()
                if has_transfers or has_distributions:
                    messages.error(
                        request,
                        "Tidak bisa mengubah jenis pupuk karena SO ini sudah memiliki "
                        "transfer gudang atau distribusi. Hapus transaksi terkait terlebih dahulu."
                    )
                    return render(request, 'gudang/so_form.html', {
                        'form': form, 'formset': formset,
                        'title': 'Edit Penebusan (SO)', 'edit_mode': True,
                    })
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
                messages.success(request, f"Penebusan SO {so.so_number} berhasil diperbarui!")
                return redirect('so_list')
            except Exception as e:
                messages.error(request, f"Terjadi kesalahan: {e}")
        else:
            messages.error(request, "Gagal menyimpan. Periksa inputan bertanda merah.")
    else:
        form = SalesOrderForm(instance=so)
        formset = AllocationFormSet(instance=so)
        if kab:
            for f in formset.forms:
                f.fields['kecamatan'].queryset = f.fields['kecamatan'].queryset.filter(kabupaten=kab)

    return render(request, 'gudang/so_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Edit Penebusan (SO)',
        'edit_mode': True,
    })

# ==========================================
# 2. MODUL TRANSFER (TARIK KE GUDANG)
# ==========================================
@login_required
def transfer_list(request):
    """Riwayat Perpindahan Stok (Virtual -> Fisik)"""
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    transfers = WarehouseTransfer.objects.select_related('source_so__jenis_pupuk') \
                                         .order_by('-date')
    if kab:
        transfers = transfers.filter(source_so__allocations__kecamatan__kabupaten=kab).distinct()
    return render(request, 'gudang/transfer_list.html', {
        'transfers': transfers,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })

@login_required
def transfer_create(request):
    """Form menarik stok dari Virtual SO ke Fisik Gudang"""
    kab = get_scope_kabupaten(request)
    so_qs = SalesOrder.objects.filter(is_closed=False)
    if kab:
        so_qs = so_qs.filter(allocations__kecamatan__kabupaten=kab).distinct()

    if request.method == 'POST':
        form = WarehouseTransferForm(request.POST)
        form.fields['source_so'].queryset = so_qs
        if form.is_valid():
            try:
                # Validasi logika (Cukup stok kah?) sudah ditangani di models.py clean()
                # Form.is_valid() otomatis memanggil clean() tersebut.
                with transaction.atomic():
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
        form.fields['source_so'].queryset = so_qs
    
    return render(request, 'gudang/transfer_form.html', {'form': form, 'title': 'Tarik Stok ke Gudang'})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def transfer_edit(request, pk):
    """Edit Transfer Gudang (superadmin only)."""
    transfer = get_object_or_404(WarehouseTransfer, pk=pk)

    if request.method == 'POST':
        form = WarehouseTransferForm(request.POST, instance=transfer)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, "Data transfer berhasil diperbarui!")
                return redirect('transfer_list')
            except Exception as e:
                messages.error(request, f"Error: {e}")
        else:
            messages.error(request, "Gagal menyimpan. Periksa pesan error di bawah.")
    else:
        form = WarehouseTransferForm(instance=transfer)

    return render(request, 'gudang/transfer_form.html', {
        'form': form,
        'title': 'Edit Transfer Gudang',
        'edit_mode': True,
    })

# ==========================================
# 3. MODUL DISTRIBUSI (SURAT JALAN)
# ==========================================


def validate_distribution_items(kios, dist_date, items_clean, existing_items=None):
    """Validasi stok virtual/fisik, kuota kios, dan harga master untuk kumpulan item.
    
    Args:
        existing_items: List of existing DistributionItem objects (for edit mode).
                        Their tonnage will be added back to balances before checking.
    """
    if not items_clean:
        raise ValidationError("Minimal 1 item pupuk diperlukan.")

    # Validasi harga: pastikan setiap jenis pupuk punya harga > 0
    kab = getattr(getattr(kios, 'kecamatan', None), 'kabupaten', None)
    checked_jenis = set()
    for item in items_clean:
        jenis = item['jenis_pupuk']
        if jenis.id not in checked_jenis:
            checked_jenis.add(jenis.id)
            price_obj = get_price_for(jenis, kab)
            if not price_obj or price_obj.price_sell <= 0 or price_obj.price_buy <= 0:
                raise ValidationError(
                    f"Harga {jenis.name} belum dikonfigurasi atau masih 0 untuk kabupaten ini. "
                    f"Silakan set di Master Harga terlebih dahulu."
                )

    so_balance = {}
    physical_balance = {}
    quota_balance = {}

    # EDIT MODE: Add back old items' values to balances
    if existing_items:
        old_dist = existing_items[0].distribution
        old_kios = old_dist.kios
        old_year = old_dist.date.year

        for old_item in existing_items:
            # Stock balances (global) — always add back
            if old_item.source_type == 'VIRTUAL' and old_item.source_so:
                so_id = old_item.source_so_id
                if so_id not in so_balance:
                    so_balance[so_id] = old_item.source_so.get_virtual_balance()
                so_balance[so_id] += old_item.tonnage
            elif old_item.source_type == 'PHYSICAL':
                key = old_item.jenis_pupuk_id
                if key not in physical_balance:
                    agg = StockCard.objects.filter(jenis_pupuk_id=key, stock_type='PHYSICAL').aggregate(
                        total_in=Sum('qty_in'), total_out=Sum('qty_out'))
                    physical_balance[key] = (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))
                physical_balance[key] += old_item.tonnage

            # Quota: only add back if same kios and year
            if old_kios == kios and old_year == dist_date.year:
                qkey = (old_item.jenis_pupuk_id, dist_date.year)
                if qkey not in quota_balance:
                    alloc = KiosAllocation.objects.filter(
                        kios=kios, jenis_pupuk_id=old_item.jenis_pupuk_id, year=dist_date.year
                    ).first()
                    if alloc:
                        quota_balance[qkey] = alloc.quota_remaining
                if qkey in quota_balance:
                    quota_balance[qkey] += old_item.tonnage

    for item in items_clean:
        jenis = item['jenis_pupuk']
        ton = item.get('tonnage') or Decimal('0')
        source_type = item.get('source_type')
        so = item.get('source_so')

        if source_type == 'VIRTUAL':
            if not so:
                raise ValidationError("Pilih SO untuk sumber stok Pabrik.")
            # Validasi kritis: jenis pupuk item HARUS sama dengan jenis pupuk SO
            if so.jenis_pupuk_id != jenis.id:
                raise ValidationError(
                    f"Jenis pupuk {jenis.name} tidak cocok dengan SO {so.so_number} "
                    f"(jenis: {so.jenis_pupuk.name}). Pastikan jenis pupuk sesuai."
                )
            if so.id not in so_balance:
                so_balance[so.id] = so.get_virtual_balance()
            so_balance[so.id] -= ton
            if so_balance[so.id] < 0:
                raise ValidationError(f"Stok virtual SO {so.so_number} tidak cukup (sisa {so_balance[so.id] + ton:,.2f} Ton).")
        else:
            key = jenis.id
            if key not in physical_balance:
                agg = StockCard.objects.filter(jenis_pupuk=jenis, stock_type='PHYSICAL').aggregate(
                    total_in=Sum('qty_in'),
                    total_out=Sum('qty_out'),
                )
                physical_balance[key] = (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))
            physical_balance[key] -= ton
            if physical_balance[key] < 0:
                raise ValidationError(f"Stok fisik {jenis.code} tidak cukup (sisa {physical_balance[key] + ton:,.2f} Ton).")

        qkey = (jenis.id, dist_date.year)
        if qkey not in quota_balance:
            alloc = KiosAllocation.objects.filter(kios=kios, jenis_pupuk=jenis, year=dist_date.year).first()
            if not alloc:
                raise ValidationError(f"Belum ada alokasi {jenis.code} untuk tahun {dist_date.year} di kios ini.")
            quota_balance[qkey] = alloc.quota_remaining
        quota_balance[qkey] -= ton
        if quota_balance[qkey] < 0:
            raise ValidationError(f"Kuota {jenis.code} tersisa {quota_balance[qkey] + ton:,.2f} Ton, tidak cukup.")

    return True


@login_required
def distribution_list(request):
    # Tambahkan 'invoice' di select_related/prefetch agar efisien
    # Note: Karena Invoice one-to-one ke Distribution, kita akses via reverse relationship
    data_surat_jalan = Distribution.objects.select_related(
        'kios', 'armada', 'invoice'
    ).prefetch_related('items__jenis_pupuk', 'items__source_so').annotate(total_ton=Sum('items__tonnage')).order_by('-date', '-created_at')
    data_surat_jalan = scope_by_kabupaten(data_surat_jalan, request.user, 'kios__kecamatan__kabupaten')
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    return render(request, 'gudang/distribution_list.html', {
        'dist_list': data_surat_jalan,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })

@login_required
def distribution_create(request):
    kab = get_scope_kabupaten(request)
    so_qs = SalesOrder.objects.filter(is_closed=False)
    if kab:
        so_qs = so_qs.filter(allocations__kecamatan__kabupaten=kab).distinct()

    order_items_qs = OrderNoteItem.objects.filter(order__is_deleted=False, order__status=OrderNote.STATUS_OPEN)
    if kab:
        order_items_qs = order_items_qs.filter(order__kios__kecamatan__kabupaten=kab)

    delivered_map = {
        row['order_item']: row['total'] or Decimal('0')
        for row in DistributionItem.objects.filter(order_item__isnull=False)
        .values('order_item').annotate(total=Sum('tonnage'))
    }

    def remaining_order_qty(oi):
        delivered = delivered_map.get(oi.id, Decimal('0'))
        remaining = (oi.tonnage or Decimal('0')) - delivered
        return remaining if remaining > 0 else Decimal('0')

    open_order_items = []
    for oi in order_items_qs.select_related('order__kios__kecamatan__kabupaten', 'order__kecamatan', 'jenis_pupuk'):
        rem = remaining_order_qty(oi)
        if rem > 0:
            oi.remaining_qty = rem
            open_order_items.append(oi)

    prefill_order_item = None
    prefill_initial = None
    prefill_kios = None
    prefill_dates = {}
    if request.method != 'POST':
        oid_raw = request.GET.get('order_item')
        try:
            oid = int(oid_raw) if oid_raw else None
        except (TypeError, ValueError):
            oid = None
        if oid:
            prefill_order_item = next((o for o in open_order_items if o.id == oid), None)
            if prefill_order_item:
                prefill_kios = prefill_order_item.order.kios
                prefill_initial = [{
                    'jenis_pupuk': prefill_order_item.jenis_pupuk,
                    'tonnage': prefill_order_item.remaining_tonnage,
                    'order_item': prefill_order_item.id,
                }]
                today = timezone.now().date()
                prefill_dates = {'date': today, 'pkp_date': today}

    if request.method == 'POST':
        form = DistributionForm(request.POST)
        kios_selected = form.data.get('kios') or None
        formset = DistributionItemFormSet(request.POST, prefix='items', kios=kios_selected)
        if kab:
            form.fields['kios'].queryset = Kios.objects.filter(is_active=True, kecamatan__kabupaten=kab)
        # Batasi SO di formset
        for f in formset.forms:
            f.fields['source_so'].queryset = so_qs
            f.fields['order_item'].queryset = order_items_qs

        if form.is_valid() and formset.is_valid():
            items_clean = []
            for f in formset.cleaned_data:
                if not f or f.get('DELETE'):
                    continue
                # Anggap kosong jika semua bidang utama belum diisi
                if not any([
                    f.get('jenis_pupuk'),
                    f.get('source_type'),
                    f.get('source_so'),
                    f.get('order_item'),
                    f.get('tonnage'),
                ]):
                    continue
                items_clean.append(f)
            if not items_clean:
                messages.error(request, "Minimal satu item pupuk diperlukan.")
                return render(request, 'gudang/distribution_form.html', {
                    'form': form,
                    'formset': formset,
                    'open_order_items': open_order_items,
                })
            try:
                validate_distribution_items(form.cleaned_data['kios'], form.cleaned_data['date'], items_clean)
            except ValidationError as exc:
                messages.error(request, exc.message)
            else:
                try:
                    with transaction.atomic():
                        dist = form.save(commit=False)
                        # Legacy header fields diisi dari item pertama untuk kompatibilitas lama
                        first = items_clean[0]
                        dist.source_type = first['source_type']
                        dist.jenis_pupuk = first['jenis_pupuk']
                        dist.tonnage = sum(i['tonnage'] for i in items_clean)
                        dist.source_so = first.get('source_so')
                        dist.save()

                        formset.instance = dist
                        formset.save()

                    messages.success(request, f"Surat Jalan {dist.no_surat_jalan} berhasil diterbitkan.")
                    return redirect('distribution_list')
                except IntegrityError:
                    messages.error(request, "Kuota atau stok tidak mencukupi (transaksi lain mungkin baru saja memotong). Silakan coba lagi.")
                except Exception as e:
                    messages.error(request, f"Gagal Simpan: {e}")
        else:
            messages.error(request, "Form tidak valid. Periksa kolom yang bertanda merah.")
    else:
        form = DistributionForm(initial=prefill_dates if prefill_dates else None)
        formset = DistributionItemFormSet(prefix='items', kios=prefill_kios.id if prefill_kios else None, initial=prefill_initial)
        if kab:
            form.fields['kios'].queryset = Kios.objects.filter(is_active=True, kecamatan__kabupaten=kab)
        if prefill_kios and kab and prefill_kios.kecamatan.kabupaten != kab:
            messages.error(request, "Pesanan tidak sesuai kabupaten akses Anda.")
        if prefill_kios:
            form.fields['kios'].initial = prefill_kios.id
        for f in formset.forms:
            f.fields['source_so'].queryset = so_qs
            f.fields['order_item'].queryset = order_items_qs

    # Build SO data map: {so_id: {jenis_pupuk_id, balance}} untuk filter & info sisa di JS
    so_data_map = {}
    for so in so_qs.select_related('jenis_pupuk'):
        so_data_map[str(so.id)] = {
            'jenis_id': str(so.jenis_pupuk_id),
            'balance': str(so.get_virtual_balance()),
        }

    return render(request, 'gudang/distribution_form.html', {
        'form': form,
        'formset': formset,
        'open_order_items': open_order_items,
        'so_data_json': json.dumps(so_data_map),
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def distribution_edit(request, pk):
    """Edit Distribusi / Surat Jalan (superadmin only)."""
    dist = get_object_or_404(Distribution, pk=pk)
    kab = get_scope_kabupaten(request)

    # SO queryset: open SOs + SOs already referenced by this distribution's items
    used_so_ids = list(dist.items.filter(source_so__isnull=False).values_list('source_so_id', flat=True))
    so_qs = SalesOrder.objects.filter(is_closed=False)
    if used_so_ids:
        so_qs = so_qs | SalesOrder.objects.filter(pk__in=used_so_ids)
    so_qs = so_qs.distinct()
    if kab:
        so_qs = so_qs.filter(allocations__kecamatan__kabupaten=kab).distinct()

    # Snapshot existing items for edit-mode validation offset
    existing_items = list(dist.items.select_related('jenis_pupuk', 'source_so').all())

    if request.method == 'POST':
        form = DistributionForm(request.POST, instance=dist)
        kios_selected = form.data.get('kios') or None
        formset = DistributionItemFormSet(request.POST, prefix='items', instance=dist, kios=kios_selected)
        if kab:
            form.fields['kios'].queryset = Kios.objects.filter(is_active=True, kecamatan__kabupaten=kab)
        for f in formset.forms:
            f.fields['source_so'].queryset = so_qs

        if form.is_valid() and formset.is_valid():
            items_clean = []
            for f in formset.cleaned_data:
                if not f or f.get('DELETE'):
                    continue
                if not any([f.get('jenis_pupuk'), f.get('source_type'), f.get('source_so'), f.get('order_item'), f.get('tonnage')]):
                    continue
                items_clean.append(f)
            if not items_clean:
                messages.error(request, "Minimal satu item pupuk diperlukan.")
            else:
                try:
                    validate_distribution_items(
                        form.cleaned_data['kios'],
                        form.cleaned_data['date'],
                        items_clean,
                        existing_items=existing_items,
                    )
                except ValidationError as exc:
                    messages.error(request, exc.message)
                else:
                    try:
                        # Snapshot kios/year SEBELUM form.save() mengubah instance
                        old_kios_id = dist.kios_id
                        old_year = dist.date.year

                        with transaction.atomic():
                            dist_obj = form.save(commit=False)
                            first = items_clean[0]
                            dist_obj.source_type = first['source_type']
                            dist_obj.jenis_pupuk = first['jenis_pupuk']
                            dist_obj.tonnage = sum(i['tonnage'] for i in items_clean)
                            dist_obj.source_so = first.get('source_so')
                            dist_obj.save()
                            formset.save()

                            # ── KOREKSI KUOTA: Jika kios atau tahun berubah ──
                            # Signal per-item menggunakan distribution.kios (baru)
                            # untuk restore kuota lama — ini salah jika kios berubah.
                            # Koreksi: transfer kuota dari kios/tahun baru ke lama.
                            new_kios_id = dist_obj.kios_id
                            new_year = dist_obj.date.year
                            if old_kios_id != new_kios_id or old_year != new_year:
                                for old_item in existing_items:
                                    jid = old_item.jenis_pupuk_id
                                    # Kembalikan ke alokasi kios/tahun LAMA
                                    alloc_old = KiosAllocation.objects.select_for_update().filter(
                                        kios_id=old_kios_id, jenis_pupuk_id=jid, year=old_year
                                    ).first()
                                    if alloc_old:
                                        alloc_old.quota_remaining += old_item.tonnage
                                        alloc_old.save(update_fields=['quota_remaining'])
                                    # Balik koreksi salah di alokasi kios/tahun BARU
                                    alloc_new = KiosAllocation.objects.select_for_update().filter(
                                        kios_id=new_kios_id, jenis_pupuk_id=jid, year=new_year
                                    ).first()
                                    if alloc_new:
                                        alloc_new.quota_remaining -= old_item.tonnage
                                        alloc_new.save(update_fields=['quota_remaining'])
                        messages.success(request, f"Surat Jalan {dist.no_surat_jalan} berhasil diperbarui.")
                        return redirect('distribution_list')
                    except IntegrityError:
                        messages.error(request, "Kuota atau stok tidak mencukupi. Silakan coba lagi.")
                    except Exception as e:
                        messages.error(request, f"Gagal Simpan: {e}")
        else:
            messages.error(request, "Form tidak valid. Periksa kolom yang bertanda merah.")
    else:
        form = DistributionForm(instance=dist)
        formset = DistributionItemFormSet(prefix='items', instance=dist, kios=dist.kios_id)
        if kab:
            form.fields['kios'].queryset = Kios.objects.filter(is_active=True, kecamatan__kabupaten=kab)
        for f in formset.forms:
            f.fields['source_so'].queryset = so_qs

    # SO data map for JS
    so_data_map = {}
    for so in so_qs.select_related('jenis_pupuk'):
        so_data_map[str(so.id)] = {
            'jenis_id': str(so.jenis_pupuk_id),
            'balance': str(so.get_virtual_balance()),
        }

    return render(request, 'gudang/distribution_form.html', {
        'form': form,
        'formset': formset,
        'open_order_items': [],
        'so_data_json': json.dumps(so_data_map),
        'edit_mode': True,
    })

# ==========================================
# 4. MODUL KARTU STOK & OPNAME
# ==========================================
@login_required
def stock_card_list(request):
    """
    Kartu Stok (Ledger) dengan Running Balance, enriched data, dan
    server-side pagination enterprise-grade.
    """
    # 1. SETUP & PARAMETER
    cards = []
    saldo_akhir = Decimal('0')

    jenis_code = request.GET.get('jenis', 'NPK')
    stock_filter = request.GET.get('stock', 'PHYSICAL')
    per_page = request.GET.get('per_page', '25')
    page_number = request.GET.get('page', '1')
    search_q = request.GET.get('q', '').strip()

    try:
        per_page = int(per_page)
        if per_page not in (10, 25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    # 2. JENIS PUPUK
    jenis_pupuk = JenisPupuk.objects.filter(code__iexact=jenis_code).first()

    total_count = 0
    page_obj = None

    if jenis_pupuk:
        # 3. QUERY & RUNNING BALANCE (harus hitung seluruh dataset dulu)
        raw_cards = StockCard.objects.filter(
            jenis_pupuk=jenis_pupuk,
            stock_type=stock_filter
        ).order_by('date', 'created_at')

        # Hitung running balance untuk semua data
        for card in raw_cards:
            saldo_akhir += (card.qty_in or Decimal('0')) - (card.qty_out or Decimal('0'))
            card.current_balance = saldo_akhir
            cards.append(card)

        cards.reverse()  # terbaru di atas

        # 4. ENRICH: parse ref → lookup SO, Kios, Kecamatan
        _enrich_stock_cards(cards)

        # 5. SEARCH FILTER (client-side text match on enriched data)
        if search_q:
            q_lower = search_q.lower()
            cards = [c for c in cards if (
                q_lower in (c.extra_so_number or '').lower()
                or q_lower in (c.extra_kios or '').lower()
                or q_lower in (c.extra_kecamatan or '').lower()
                or q_lower in (c.description or '').lower()
                or q_lower in (c.reference_number or '').lower()
            )]

        total_count = len(cards)

        # 6. PAGINATION
        paginator = Paginator(cards, per_page)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        cards = list(page_obj)

    return render(request, 'gudang/stock_card_list.html', {
        'cards': cards,
        'page_obj': page_obj,
        'total_count': total_count,
        'per_page': per_page,
        'jenis_selected': jenis_code,
        'saldo_akhir': saldo_akhir,
        'stock_selected': stock_filter,
        'search_q': search_q,
        'now': timezone.now(),
        'jenis_list': JenisPupuk.objects.filter(is_active=True).order_by('name'),
    })


def _enrich_stock_cards(cards):
    """
    Batch-enrich StockCard list with SO number, Kios name & Kecamatan name.
    Parses reference_number to resolve related objects in minimal queries.
    """
    # Collect IDs by type
    so_ids = set()
    trf_ids = set()
    dist_item_ids = set()
    dist_ids_legacy = set()

    ref_pattern_sj_item = re.compile(r'^SJ-(\d+)-(\d+)-')
    ref_pattern_sj_legacy = re.compile(r'^SJ-(\d+)$')
    ref_pattern_trf = re.compile(r'^TRF-(\d+)-')
    ref_pattern_so = re.compile(r'^SO-(\d+)$')

    for card in cards:
        ref = card.reference_number or ''
        m = ref_pattern_sj_item.match(ref)
        if m:
            dist_item_ids.add(int(m.group(2)))
            continue
        m = ref_pattern_sj_legacy.match(ref)
        if m:
            dist_ids_legacy.add(int(m.group(1)))
            continue
        m = ref_pattern_trf.match(ref)
        if m:
            trf_ids.add(int(m.group(1)))
            continue
        m = ref_pattern_so.match(ref)
        if m:
            so_ids.add(int(m.group(1)))

    # Batch queries
    so_map = {}
    if so_ids:
        for so in SalesOrder.objects.filter(id__in=so_ids):
            so_map[so.id] = so

    trf_map = {}
    if trf_ids:
        for trf in WarehouseTransfer.objects.filter(id__in=trf_ids).select_related('source_so'):
            trf_map[trf.id] = trf

    item_map = {}
    if dist_item_ids:
        for item in DistributionItem.objects.filter(id__in=dist_item_ids).select_related(
            'distribution__kios__kecamatan', 'source_so'
        ):
            item_map[item.id] = item

    dist_map = {}
    if dist_ids_legacy:
        for dist in Distribution.objects.filter(id__in=dist_ids_legacy).select_related(
            'kios__kecamatan', 'source_so'
        ):
            dist_map[dist.id] = dist

    # Annotate each card
    for card in cards:
        card.extra_so_number = ''
        card.extra_kios = ''
        card.extra_kecamatan = ''

        ref = card.reference_number or ''

        m = ref_pattern_sj_item.match(ref)
        if m:
            item = item_map.get(int(m.group(2)))
            if item:
                if item.source_so:
                    card.extra_so_number = item.source_so.so_number
                card.extra_kios = item.distribution.kios.name
                card.extra_kecamatan = item.distribution.kios.kecamatan.name
            continue

        m = ref_pattern_sj_legacy.match(ref)
        if m:
            dist = dist_map.get(int(m.group(1)))
            if dist:
                if dist.source_so:
                    card.extra_so_number = dist.source_so.so_number
                card.extra_kios = dist.kios.name
                card.extra_kecamatan = dist.kios.kecamatan.name
            continue

        m = ref_pattern_trf.match(ref)
        if m:
            trf = trf_map.get(int(m.group(1)))
            if trf and trf.source_so:
                card.extra_so_number = trf.source_so.so_number
            continue

        m = ref_pattern_so.match(ref)
        if m:
            so = so_map.get(int(m.group(1)))
            if so:
                card.extra_so_number = so.so_number


@login_required
def stock_card_export_physical(request):
    """Export PDF stok per bulan (fisik atau virtual)."""
    stock_type = request.GET.get('stock', 'PHYSICAL')
    if stock_type not in ('PHYSICAL', 'VIRTUAL'):
        stock_type = 'PHYSICAL'

    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except (TypeError, ValueError):
        year = timezone.now().year
        month = timezone.now().month

    start_date = timezone.datetime(year, month, 1).date()
    if month == 12:
        end_date = timezone.datetime(year + 1, 1, 1).date()
    else:
        end_date = timezone.datetime(year, month + 1, 1).date()

    qs = StockCard.objects.filter(
        stock_type=stock_type,
        date__gte=start_date,
        date__lt=end_date
    ).select_related('jenis_pupuk').order_by('date', 'created_at')

    running = {}
    rows = []
    total_in = Decimal('0')
    total_out = Decimal('0')

    for card in qs:
        key = card.jenis_pupuk_id
        if key not in running:
            running[key] = Decimal('0')
        running[key] += (card.qty_in or Decimal('0')) - (card.qty_out or Decimal('0'))
        total_in += card.qty_in or Decimal('0')
        total_out += card.qty_out or Decimal('0')
        rows.append({
            'date': card.date,
            'jenis': card.jenis_pupuk.name,
            'desc': card.description,
            'ref': card.reference_number,
            'in': card.qty_in,
            'out': card.qty_out,
            'balance': running[key],
        })

    company = get_company_profile()  # Stock card export uses default profile
    if not company:
        messages.warning(request, "Profil perusahaan belum diatur. Silakan isi di menu Pengaturan.")
    export_date = timezone.now().date()
    context = {
        'company': company,
        'rows': rows,
        'year': year,
        'month': month,
        'export_date': export_date,
        'total_in': total_in,
        'total_out': total_out,
        'total_net': total_in - total_out,
    }

    html = render_to_string('gudang/stock_card_export_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    type_label_str = 'fisik' if stock_type == 'PHYSICAL' else 'virtual'
    filename = f"stok_{type_label_str}_{year}-{month:02d}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Gagal membuat PDF.', status=500)

    return response

@login_required
@user_passes_test(lambda u: u.is_staff)
def stock_opname(request):
    """
    Input penyesuaian stok manual (ADJUST) dari hasil opname fisik.
    """
    if request.method == 'POST':
        form = StockOpnameForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            jenis = data['jenis_pupuk']
            stock_type = data['stock_type']
            actual_qty = data['actual_qty']
            opname_date = data['date']
            notes = data['notes'] or 'Penyesuaian stok fisik (Stock Opname)'

            agg = StockCard.objects.filter(jenis_pupuk=jenis, stock_type=stock_type).aggregate(
                total_in=Sum('qty_in'),
                total_out=Sum('qty_out')
            )
            current_balance = (agg['total_in'] or Decimal('0')) - (agg['total_out'] or Decimal('0'))
            diff = actual_qty - current_balance

            if diff == 0:
                messages.info(request, "Tidak ada selisih antara stok sistem dan hasil fisik.")
                return redirect('stock_card_list')

            qty_in = diff if diff > 0 else Decimal('0')
            qty_out = -diff if diff < 0 else Decimal('0')
            reference_number = f"ADJ-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            description = f"Stock Opname {stock_type.title()} {jenis.code}" if hasattr(jenis, 'code') else "Stock Opname"
            if notes:
                description = f"{description} - {notes}"

            with transaction.atomic():
                StockCard.objects.create(
                    date=opname_date,
                    jenis_pupuk=jenis,
                    stock_type=stock_type,
                    transaction_type='ADJUST',
                    reference_number=reference_number,
                    description=description[:255],
                    qty_in=qty_in,
                    qty_out=qty_out,
                )

                recompute_stock_balance(jenis.id, stock_type)

            messages.success(
                request,
                f"Opname disimpan. Selisih {diff:+,.2f} Ton dicatat sebagai ADJUST ke Kartu Stok."
            )
            return redirect('stock_card_list')
    else:
        form = StockOpnameForm()
    
    return render(request, 'gudang/stock_opname.html', {'form': form})

# ==========================================
# 5. FITUR CETAK DOKUMEN (PRINT)
# ==========================================
@login_required
def print_surat_jalan(request, pk):
    """
    View khusus untuk mencetak Surat Jalan (Mode Print Browser).
    Mengambil data perusahaan dinamis untuk Kop Surat.
    """
    dist = get_object_or_404(Distribution, pk=pk)
    # Scope check: pastikan user hanya bisa cetak surat jalan kabupaten sendiri
    kab = get_scope_kabupaten(request)
    if kab and dist.kios.kecamatan.kabupaten != kab:
        messages.error(request, "Akses ditolak: surat jalan bukan milik kabupaten Anda.")
        return redirect('distribution_list')
    dist_kab = dist.kios.kecamatan.kabupaten if dist.kios and dist.kios.kecamatan else None
    company = get_company_profile(dist_kab)
    if not company:
        messages.warning(request, "Profil perusahaan belum diatur. Silakan isi di menu Pengaturan.")
    
    context = {
        'dist': dist,
        'company': company,
        'title': f"SJ_{dist.no_surat_jalan}"
    }
    # Kita gunakan template khusus print yang bersih dari sidebar
    return render(request, 'gudang/print_surat_jalan.html', context)


# ==========================================
# 6. CATATAN ORDER
# ==========================================
@login_required
def order_note_list(request):
    orders_qs = OrderNote.objects.filter(is_deleted=False).select_related('kecamatan', 'kios').prefetch_related(
        Prefetch('items', queryset=OrderNoteItem.objects.select_related('jenis_pupuk'))
    )
    orders_qs = scope_by_kabupaten(orders_qs, request.user, 'kecamatan__kabupaten')

    delivered_map = {
        row['order_item']: row['total'] or Decimal('0')
        for row in DistributionItem.objects.filter(order_item__isnull=False)
        .values('order_item').annotate(total=Sum('tonnage'))
    }

    orders = []
    for order in orders_qs:
        remaining_any = False
        for item in order.items.all():
            delivered = delivered_map.get(item.id, Decimal('0'))
            item.delivered = delivered
            item.remaining = max(Decimal('0'), (item.tonnage or Decimal('0')) - delivered)
            if item.remaining > 0:
                remaining_any = True
        if remaining_any:
            orders.append(order)
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    return render(request, 'gudang/order_note_list.html', {
        'orders': orders,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })


@login_required
def order_note_create(request):
    kab = get_scope_kabupaten(request)
    if request.method == 'POST':
        form = OrderNoteForm(request.POST)
        formset = OrderNoteItemFormSet(request.POST, prefix='items')
        kios_qs = Kios.objects.filter(is_active=True)
        if kab:
            kios_qs = kios_qs.filter(kecamatan__kabupaten=kab)
        kios_data = list(kios_qs.values('id', 'name', 'kecamatan_id'))

        if form.is_valid() and formset.is_valid():
            items_clean = [f for f in formset.cleaned_data if f and not f.get('DELETE')]
            if not items_clean:
                messages.error(request, "Minimal 1 item pupuk diperlukan.")
            else:
                try:
                    with transaction.atomic():
                        order = form.save()
                        items = formset.save(commit=False)
                        for item in items:
                            item.order = order
                            item.save()
                        for deleted in formset.deleted_objects:
                            deleted.delete()
                        messages.success(request, "Catatan order disimpan.")
                        return redirect('order_note_list')
                except Exception as exc:
                    messages.error(request, f"Gagal simpan catatan order: {exc}")
        else:
            messages.error(request, "Periksa input yang bertanda merah.")
    else:
        form = OrderNoteForm()
        formset = OrderNoteItemFormSet(prefix='items')
        kios_qs = Kios.objects.filter(is_active=True)
        if kab:
            kios_qs = kios_qs.filter(kecamatan__kabupaten=kab)
        kios_data = list(kios_qs.values('id', 'name', 'kecamatan_id'))

    if kab:
        form.fields['kecamatan'].queryset = form.fields['kecamatan'].queryset.filter(kabupaten=kab)
        form.fields['kios'].queryset = form.fields['kios'].queryset.filter(kecamatan__kabupaten=kab)

    return render(request, 'gudang/order_note_form.html', {
        'form': form,
        'formset': formset,
        'kios_data': kios_data,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def order_note_edit(request, pk):
    """Edit Catatan Order (superadmin only)."""
    order = get_object_or_404(OrderNote, pk=pk, is_deleted=False)
    kab = get_scope_kabupaten(request)

    if request.method == 'POST':
        form = OrderNoteForm(request.POST, instance=order)
        formset = OrderNoteItemFormSet(request.POST, prefix='items', instance=order)
        kios_qs = Kios.objects.filter(is_active=True)
        if kab:
            kios_qs = kios_qs.filter(kecamatan__kabupaten=kab)
        kios_data = list(kios_qs.values('id', 'name', 'kecamatan_id'))

        if form.is_valid() and formset.is_valid():
            items_clean = [f for f in formset.cleaned_data if f and not f.get('DELETE')]
            if not items_clean:
                messages.error(request, "Minimal 1 item pupuk diperlukan.")
            else:
                try:
                    with transaction.atomic():
                        form.save()
                        formset.save()
                    messages.success(request, "Catatan order berhasil diperbarui.")
                    return redirect('order_note_list')
                except Exception as exc:
                    messages.error(request, f"Gagal simpan: {exc}")
        else:
            messages.error(request, "Periksa input yang bertanda merah.")
    else:
        form = OrderNoteForm(instance=order)
        formset = OrderNoteItemFormSet(prefix='items', instance=order)
        kios_qs = Kios.objects.filter(is_active=True)
        if kab:
            kios_qs = kios_qs.filter(kecamatan__kabupaten=kab)
        kios_data = list(kios_qs.values('id', 'name', 'kecamatan_id'))

    if kab:
        form.fields['kecamatan'].queryset = form.fields['kecamatan'].queryset.filter(kabupaten=kab)
        form.fields['kios'].queryset = form.fields['kios'].queryset.filter(kecamatan__kabupaten=kab)

    return render(request, 'gudang/order_note_form.html', {
        'form': form,
        'formset': formset,
        'kios_data': kios_data,
        'edit_mode': True,
    })


@login_required
def order_note_complete(request, pk):
    order = get_object_or_404(OrderNote, pk=pk, is_deleted=False)
    # Scope check: pastikan user hanya bisa menutup order kabupaten sendiri
    kab = get_scope_kabupaten(request)
    if kab and order.kecamatan and order.kecamatan.kabupaten != kab:
        messages.error(request, "Akses ditolak: order bukan milik kabupaten Anda.")
        return redirect('order_note_list')
    if request.method != 'POST':
        messages.error(request, "Gunakan tombol selesai untuk menutup order.")
        return redirect('order_note_list')

    order.mark_done()
    messages.success(request, "Order ditandai selesai dan disembunyikan.")
    return redirect('order_note_list')