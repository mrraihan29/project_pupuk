from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Prefetch
from django.utils import timezone

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
from core.utils import scope_by_kabupaten, get_scope_kabupaten

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
    kab = get_scope_kabupaten(request)
    if kab:
        # Batasi pilihan kecamatan di formset sesuai kabupaten user
        for form_alloc in formset.forms:
            form_alloc.fields['kecamatan'].queryset = form_alloc.fields['kecamatan'].queryset.filter(kabupaten=kab)
    
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
    kab = get_scope_kabupaten(request)
    transfers = WarehouseTransfer.objects.select_related('source_so__jenis_pupuk') \
                                         .order_by('-date')
    if kab:
        transfers = transfers.filter(source_so__allocations__kecamatan__kabupaten=kab).distinct()
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


def validate_distribution_items(kios, dist_date, items_clean):
    """Validasi stok virtual/fisik dan kuota kios untuk kumpulan item."""
    if not items_clean:
        raise ValidationError("Minimal 1 item pupuk diperlukan.")

    so_balance = {}
    physical_balance = {}
    quota_balance = {}

    for item in items_clean:
        jenis = item['jenis_pupuk']
        ton = item.get('tonnage') or Decimal('0')
        source_type = item.get('source_type')
        so = item.get('source_so')

        if source_type == 'VIRTUAL':
            if not so:
                raise ValidationError("Pilih SO untuk sumber stok Pabrik.")
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
    for oi in order_items_qs.select_related('order__kios__kecamatan__kabupaten', 'jenis_pupuk'):
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

    return render(request, 'gudang/distribution_form.html', {
        'form': form,
        'formset': formset,
        'open_order_items': open_order_items,
    })

# ==========================================
# 4. MODUL KARTU STOK & OPNAME
# ==========================================
@login_required
def stock_card_list(request):
    """
    Kartu Stok (Ledger) dengan Running Balance.
    Versi Anti-Error UnboundLocal.
    """
    # 1. SETUP DEFAULT VARIABLE (Wajib di paling atas)
    cards = []
    saldo_akhir = 0
    jenis_pupuk = None # Inisialisasi awal supaya tidak UnboundLocalError
    
    # 2. Ambil Parameter URL
    jenis_code = request.GET.get('jenis', 'NPK') 
    
    # 3. Cari Object Jenis Pupuk (Safe Query)
    # Gunakan filter().first() -> Return Object atau None (Tidak akan error crash)
    jenis_pupuk = JenisPupuk.objects.filter(name__iexact=jenis_code).first()
    
    # 4. Logic Data (Hanya jalan jika jenis_pupuk DITEMUKAN)
    if jenis_pupuk:
        # Ambil Transaksi (Urut dari lama ke baru untuk hitung saldo)
        raw_cards = StockCard.objects.filter(jenis_pupuk=jenis_pupuk).order_by('date', 'created_at')
        
        # Hitung Running Balance
        for card in raw_cards:
            saldo_akhir += card.qty_in   # Masuk menambah
            saldo_akhir -= card.qty_out  # Keluar mengurangi
            
            # Tempelkan hasil ke object sementara
            card.current_balance = saldo_akhir
            cards.append(card)
            
        # Balik urutan agar yang terbaru muncul di atas (DESC)
        cards.reverse()
    
    # 5. Render Template
    return render(request, 'gudang/stock_card_list.html', {
        'cards': cards,
        'jenis_selected': jenis_code, # Kirim string kode (NPK/UREA) ke template
        'saldo_akhir': saldo_akhir
    })

@login_required
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
    company = CompanyProfile.objects.first() # Ambil profil perusahaan
    
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
def order_note_complete(request, pk):
    order = get_object_or_404(OrderNote, pk=pk, is_deleted=False)
    if request.method != 'POST':
        messages.error(request, "Gunakan tombol selesai untuk menutup order.")
        return redirect('order_note_list')

    order.mark_done()
    messages.success(request, "Order ditandai selesai dan disembunyikan.")
    return redirect('order_note_list')