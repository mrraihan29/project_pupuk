from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from datetime import date
from django.utils import timezone
from decimal import Decimal
# Import Models & Forms
from .models import Invoice, Payment, BiayaOperasional
from .forms import PaymentForm, BiayaOperasionalForm
from core.models import Armada, CompanyProfile, Kabupaten
from core.utils import get_scope_kabupaten, scope_by_kabupaten
from core.utils import get_price_for

# Decorator Custom (Pastikan Anda punya file ini, jika tidak, hapus baris ini)
from core.decorators import owner_required

# ==========================================
# 1. INVOICE & PAYMENT (PIUTANG)
# ==========================================
@login_required
def invoice_list(request):
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    invoices = Invoice.objects.select_related('distribution__kios__kecamatan__kabupaten').prefetch_related('payments').order_by('status', 'due_date')
    if kab:
        invoices = invoices.filter(distribution__kios__kecamatan__kabupaten=kab)

    agg = invoices.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(
        total_amount=Sum('total_amount'),
        total_paid=Sum('total_paid')
    )

    sisa_piutang = (agg['total_amount'] or 0) - (agg['total_paid'] or 0)

    return render(request, 'keuangan/invoice_list.html', {
        'invoices': invoices,
        'total_piutang': sisa_piutang,
        'today': date.today(),
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })

@login_required
def payment_create(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    # Scope check: non-superuser hanya bisa bayar invoice kabupaten sendiri
    if not request.user.is_superuser:
        kab = get_scope_kabupaten(request)
        inv_kab = getattr(getattr(getattr(invoice.distribution.kios, 'kecamatan', None), 'kabupaten', None), 'pk', None)
        if kab and inv_kab and kab.pk != inv_kab:
            messages.error(request, "Anda tidak memiliki akses ke invoice ini.")
            return redirect('invoice_list')

    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES, invoice=invoice)
        if form.is_valid():
            with transaction.atomic():
                # Lock invoice untuk mencegah race condition (2 pembayaran simultan)
                locked_invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
                # Re-validate remaining balance setelah lock
                remaining = locked_invoice.remaining_balance or Decimal('0')
                amount = form.cleaned_data['amount']
                if amount > remaining:
                    messages.error(request, f"Sisa tagihan hanya Rp {remaining:,.0f}. Mungkin ada pembayaran lain yang baru masuk.")
                    return render(request, 'keuangan/payment_form.html', {'form': form, 'invoice': invoice})
                pay = form.save(commit=False)
                pay.invoice = locked_invoice
                pay.save()
            messages.success(request, "Pembayaran berhasil dicatat.")
            return redirect('invoice_list')
    else:
        form = PaymentForm(invoice=invoice)
    return render(request, 'keuangan/payment_form.html', {'form': form, 'invoice': invoice})


@login_required
@require_http_methods(["POST"])
def payment_void(request, pk):
    """Batalkan (void) pembayaran. Signal otomatis mengurangi total_paid invoice."""
    payment = get_object_or_404(Payment, pk=pk)
    invoice = payment.invoice

    # Scope check
    if not request.user.is_superuser:
        kab = get_scope_kabupaten(request)
        inv_kab = getattr(getattr(getattr(invoice.distribution.kios, 'kecamatan', None), 'kabupaten', None), 'pk', None)
        if kab and inv_kab and kab.pk != inv_kab:
            messages.error(request, "Anda tidak memiliki akses ke pembayaran ini.")
            return redirect('invoice_list')

    if payment.status == 'VOID':
        messages.warning(request, "Pembayaran ini sudah dibatalkan sebelumnya.")
        return redirect('invoice_list')

    with transaction.atomic():
        payment.status = 'VOID'
        payment.save()  # Signal update_invoice_status akan handle delta otomatis

    messages.warning(request, f"Pembayaran Rp {payment.amount:,.0f} pada {payment.date} berhasil dibatalkan.")
    return redirect('invoice_list')


# ==========================================
# 2. BIAYA OPERASIONAL (PENGELUARAN)
# ==========================================
@login_required
def ops_list(request):
    kab = get_scope_kabupaten(request)
    kab_options = Kabupaten.objects.all().order_by('name') if request.user.is_superuser else Kabupaten.objects.none()
    ops = BiayaOperasional.objects.select_related('armada', 'kabupaten').order_by('-tanggal')
    if kab:
        ops = ops.filter(kabupaten=kab)
    return render(request, 'keuangan/ops_list.html', {
        'ops': ops,
        'kab_options': kab_options,
        'selected_kabupaten': kab.id if kab else None,
    })

@login_required
def ops_create(request):
    kab = get_scope_kabupaten(request)
    if request.method == 'POST':
        # ===>>> WAJIB ADA: request.FILES <<<===
        form = BiayaOperasionalForm(request.POST, request.FILES)
        if kab and not request.user.is_superuser:
            form.fields['kabupaten'].queryset = form.fields['kabupaten'].queryset.filter(pk=kab.pk)
            form.data = form.data.copy()
            form.data['kabupaten'] = kab.pk
        
        if form.is_valid():
            biaya = form.save(commit=False)
            if kab and not request.user.is_superuser:
                biaya.kabupaten = kab
            biaya.status = 'PROSES'  # Default status menunggu approval
            biaya.save()
            messages.success(request, 'Pengeluaran berhasil dicatat, menunggu persetujuan.')
            return redirect('ops_list')
        else:
            # Ini akan memunculkan error di HTML jika ada input salah
            messages.error(request, 'Gagal menyimpan. Periksa form kembali.')
    else:
        form = BiayaOperasionalForm(initial={'tanggal': timezone.localdate(), 'kabupaten': kab.pk if kab else None})
        if kab and not request.user.is_superuser:
            form.fields['kabupaten'].queryset = form.fields['kabupaten'].queryset.filter(pk=kab.pk)

    return render(request, 'keuangan/ops_form.html', {'form': form})


@login_required
def ops_edit(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    # Hanya bisa edit jika masih berstatus PROSES
    if ops.status != 'PROSES':
        messages.error(request, "Tidak bisa mengedit biaya yang sudah disetujui/ditolak.")
        return redirect('ops_list')

    kab = get_scope_kabupaten(request)
    # Scope check: pastikan user hanya bisa edit ops kabupaten sendiri
    if kab and ops.kabupaten and ops.kabupaten != kab:
        messages.error(request, "Akses ditolak: biaya bukan milik kabupaten Anda.")
        return redirect('ops_list')
    if request.method == 'POST':
        form = BiayaOperasionalForm(request.POST, request.FILES, instance=ops)
        if kab and not request.user.is_superuser:
            form.fields['kabupaten'].queryset = form.fields['kabupaten'].queryset.filter(pk=kab.pk)
            form.data = form.data.copy()
            form.data['kabupaten'] = kab.pk
        if form.is_valid():
            biaya = form.save(commit=False)
            if kab and not request.user.is_superuser:
                biaya.kabupaten = kab
            biaya.save()
            messages.success(request, 'Pengeluaran berhasil diperbarui.')
            return redirect('ops_list')
        else:
            messages.error(request, 'Gagal menyimpan. Periksa form kembali.')
    else:
        form = BiayaOperasionalForm(instance=ops)
        if kab and not request.user.is_superuser:
            form.fields['kabupaten'].queryset = form.fields['kabupaten'].queryset.filter(pk=kab.pk)

    return render(request, 'keuangan/ops_form.html', {'form': form, 'edit_mode': True, 'ops_obj': ops})


# ==========================================
# 3. ACTION OWNER (APPROVE, REJECT & DELETE)
# ==========================================
@owner_required
@require_http_methods(["POST"])
def ops_approve(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    if ops.status != 'PROSES':
        messages.error(request, "Hanya biaya berstatus 'Menunggu Approval' yang bisa disetujui.")
        return redirect('ops_list')
    ops.status = 'SELESAI'
    ops.save()
    messages.success(request, "Biaya disetujui.")
    return redirect('ops_list')


@owner_required
@require_http_methods(["POST"])
def ops_reject(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    if ops.status != 'PROSES':
        messages.error(request, "Hanya biaya berstatus 'Menunggu Approval' yang bisa ditolak.")
        return redirect('ops_list')
    ops.status = 'TOLAK'
    ops.save()
    messages.warning(request, "Biaya ditolak.")
    return redirect('ops_list')


@owner_required
@require_http_methods(["POST"])
def ops_delete(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    ops.delete()
    messages.warning(request, "Data dihapus.")
    return redirect('ops_list')

# ==========================================
# 4. KARTU KONTROL & API
# ==========================================
@login_required
def kartu_kontrol_armada(request):
    """Riwayat Service per Mobil"""
    armada_list = Armada.objects.all()
    selected_armada = None
    logs = []
    kab = get_scope_kabupaten(request)
    
    armada_id = request.GET.get('armada_id')
    if armada_id:
        selected_armada = get_object_or_404(Armada, pk=armada_id)
        # Filter biaya kategori ARMADA untuk mobil ini
        logs = BiayaOperasional.objects.filter(
            kategori_utama='ARMADA',
            status='SELESAI',
            armada=selected_armada
        )
        if kab:
            logs = logs.filter(kabupaten=kab)
        logs = logs.order_by('-tanggal')

    return render(request, 'keuangan/kartu_kontrol.html', {
        'armada_list': armada_list,
        'selected_armada': selected_armada,
        'logs': logs
    })

@login_required
def get_armada_history(request):
    """API AJAX untuk mencegah double input service"""
    armada_id = request.GET.get('armada_id')
    if not armada_id:
        return JsonResponse({'error': 'No ID'}, status=400)

    history = BiayaOperasional.objects.filter(
        kategori_utama='ARMADA',
        status='SELESAI',
        armada_id=armada_id
    ).order_by('-tanggal')[:5]
    
    data = [{
        'tanggal': h.tanggal.strftime('%d/%m/%Y'),
        'keterangan': h.deskripsi,
        'nominal': float(h.nominal),
        'status': h.status
    } for h in history]
    
    return JsonResponse({'history': data})

@login_required
def print_invoice(request, pk):
    """
    View khusus cetak Invoice.
    """
    inv = get_object_or_404(Invoice, pk=pk)
    # Scope check: pastikan user hanya bisa cetak invoice kabupaten sendiri
    kab = get_scope_kabupaten(request)
    inv_kab = getattr(getattr(getattr(inv.distribution.kios, 'kecamatan', None), 'kabupaten', None), 'pk', None)
    if kab and inv_kab and kab.pk != inv_kab:
        messages.error(request, "Akses ditolak: invoice bukan milik kabupaten Anda.")
        return redirect('invoice_list')
    company = CompanyProfile.objects.first()
    if not company:
        messages.warning(request, "Profil perusahaan belum diatur. Silakan isi di menu Pengaturan.")
    kab = getattr(getattr(inv.distribution.kios, 'kecamatan', None), 'kabupaten', None)

    items = []
    subtotal = Decimal('0')
    for item in inv.distribution.items.select_related('jenis_pupuk'):
        # Prioritas: snapshot price (terkunci saat transaksi), fallback master price
        if item.price_sell_snapshot is not None:
            harga_per_ton = item.price_sell_snapshot
        else:
            price_obj = get_price_for(item.jenis_pupuk, kab)
            harga_per_ton = price_obj.price_sell if price_obj else Decimal('0')
        line_total = ((item.tonnage or Decimal('0')) * harga_per_ton).quantize(Decimal('1'))
        subtotal += line_total
        items.append({
            'name': item.jenis_pupuk.name,
            'tonnage': item.tonnage,
            'price': harga_per_ton.quantize(Decimal('1')),
            'total': line_total,
        })
    
    context = {
        'inv': inv,
        'company': company,
        'title': f"INV_{inv.inv_number}",
        'items': items,
        'subtotal': subtotal,
    }
    return render(request, 'keuangan/print_invoice.html', context)