from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from .models import Invoice, Payment, BiayaOperasional
from .forms import PaymentForm, BiayaOperasionalForm
from core.decorators import owner_required
# --- 1. MODUL INVOICE & PEMBAYARAN ---

def invoice_list(request):
    # Urutkan: Yang UNPAID paling atas, lalu berdasarkan Jatuh Tempo
    invoices = Invoice.objects.all().select_related('distribution__kios').order_by('status', 'due_date')
    
    # Hitung Total Piutang (Yang belum dibayar)
    total_piutang = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0
    
    return render(request, 'keuangan/invoice_list.html', {
        'invoices': invoices,
        'total_piutang': total_piutang
    })

def payment_create(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES) # request.FILES wajib untuk upload foto
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            
            # Validasi: Jangan bayar lebih dari hutang
            if payment.amount > invoice.remaining_balance:
                messages.error(request, f"Gagal! Nominal Rp {payment.amount:,.0f} melebihi sisa hutang Rp {invoice.remaining_balance:,.0f}")
            else:
                payment.save()
                messages.success(request, "Pembayaran berhasil dicatat.")
                return redirect('invoice_list')
    else:
        form = PaymentForm()

    return render(request, 'keuangan/payment_form.html', {
        'form': form,
        'invoice': invoice
    })

# --- 2. MODUL OPERASIONAL (BIAYA) ---

def ops_list(request):
    ops_costs = BiayaOperasional.objects.all().select_related('armada').order_by('-tanggal')
    return render(request, 'keuangan/ops_list.html', {'ops_costs': ops_costs})

def ops_create(request):
    if request.method == 'POST':
        form = BiayaOperasionalForm(request.POST, request.FILES)
        if form.is_valid():
            ops = form.save()
            messages.success(request, "Biaya operasional berhasil diajukan (Pending Approval).")
            return redirect('ops_list')
    else:
        form = BiayaOperasionalForm()
    
    return render(request, 'keuangan/ops_form.html', {'form': form})

# --- FITUR APPROVE (HANYA OWNER) ---
@owner_required
def ops_approve(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    ops.is_approved = True
    ops.save()
    messages.success(request, f"Biaya {ops.kategori} senilai Rp {ops.nominal} disetujui.")
    return redirect('ops_list')

# --- FITUR REJECT/HAPUS (HANYA OWNER) ---
@owner_required
def ops_delete(request, pk):
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    ops.delete()
    messages.warning(request, "Pengajuan biaya dihapus/ditolak.")
    return redirect('ops_list')

# --- API ANTI-FRAUD ---
def get_armada_history(request):
    """
    API untuk mengambil 5 riwayat pengeluaran terakhir dari armada tertentu.
    Dipanggil via AJAX saat dropdown armada berubah.
    """
    armada_id = request.GET.get('armada_id')
    if not armada_id:
        return JsonResponse({'error': 'No ID'}, status=400)

    # Ambil 5 pengeluaran terakhir (Terutama Servis & Sparepart)
    history = BiayaOperasional.objects.filter(armada_id=armada_id).order_by('-tanggal')[:5]
    
    data = []
    for h in history:
        data.append({
            'tanggal': h.tanggal.strftime('%d/%m/%Y'),
            'kategori': h.kategori,  # Use the actual value if not a choice field
            'keterangan': h.keterangan,
            'nominal': float(h.nominal),
            'status': 'Approved' if h.is_approved else 'Pending'
        })
    
    return JsonResponse({'history': data})