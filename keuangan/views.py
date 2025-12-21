from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

# IMPORT MODELS
from core.models import Armada
from .models import Invoice, Payment, BiayaOperasional
from .forms import PaymentForm, BiayaOperasionalForm

# IMPORT DECORATOR
# Pastikan core/decorators.py ada, jika tidak, hapus baris ini dan @owner_required
from core.decorators import owner_required 

# ==========================================
# 1. MODUL INVOICE & PEMBAYARAN
# ==========================================

@login_required
def invoice_list(request):
    """Menampilkan daftar tagihan ke Kios (AR)"""
    # Urutkan: Yang belum lunas (UNPAID/PARTIAL) paling atas
    invoices = Invoice.objects.all().select_related('distribution__kios').order_by('status', 'due_date')
    
    # Hitung Total Piutang (Uang yang masih di luar)
    total_piutang = Invoice.objects.filter(status__in=['UNPAID', 'PARTIAL']).aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0
    
    return render(request, 'keuangan/invoice_list.html', {
        'invoices': invoices,
        'total_piutang': total_piutang
    })

@login_required
def payment_create(request, invoice_id):
    """Mencatat pembayaran cicilan dari Kios"""
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES) # request.FILES wajib untuk bukti transfer
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            
            # Validasi: Jangan bayar lebih dari sisa hutang
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


# ==========================================
# 2. MODUL BIAYA OPERASIONAL (OPEX)
# ==========================================

@login_required
def ops_list(request):
    """Daftar semua pengeluaran (Armada & Kantor)"""
    # Ambil semua data, urutkan dari tanggal terbaru
    ops_costs = BiayaOperasional.objects.all().select_related('armada').order_by('-tanggal')
    return render(request, 'keuangan/ops_list.html', {'ops_costs': ops_costs})

@login_required
def ops_create(request):
    """Form Input Pengeluaran Baru"""
    if request.method == 'POST':
        form = BiayaOperasionalForm(request.POST, request.FILES)
        if form.is_valid():
            ops = form.save(commit=False)
            
            # --- FIX BUG AUTO-APPROVE ---
            # Kita paksa status jadi 'PROSES' agar tombol Approve muncul di tabel
            ops.status = 'PROSES' 
            
            # --- VALIDASI TAMBAHAN ---
            # Jika user pilih Kategori ARMADA tapi lupa pilih Mobil, kita tolak!
            if ops.kategori_utama == 'ARMADA' and not ops.armada:
                messages.error(request, "Wajib memilih Armada/Mobil jika kategori adalah Biaya Armada!")
                return render(request, 'keuangan/ops_form.html', {'form': form})

            ops.save()
            
            messages.success(request, "Biaya operasional berhasil diajukan (Menunggu Approval).")
            return redirect('ops_list')
    else:
        form = BiayaOperasionalForm()
    
    return render(request, 'keuangan/ops_form.html', {'form': form})


# ==========================================
# 3. FITUR APPROVAL & ACTION (OWNER ONLY)
# ==========================================

@owner_required
def ops_approve(request, pk):
    """Tombol 'Setujui' mengubah status menjadi SELESAI"""
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    
    # Update status menjadi SELESAI
    ops.status = 'SELESAI'
    ops.save() # Tanggal selesai otomatis terisi di models.py save() method
    
    messages.success(request, f"Biaya {ops.get_kategori_utama_display()} berhasil disetujui/diselesaikan.")
    return redirect('ops_list')

@owner_required
def ops_delete(request, pk):
    """Hapus data pengeluaran"""
    ops = get_object_or_404(BiayaOperasional, pk=pk)
    ops.delete()
    messages.warning(request, "Data pengeluaran berhasil dihapus.")
    return redirect('ops_list')


# ==========================================
# 4. FITUR KARTU KONTROL ARMADA (SERVICE LOG)
# ==========================================

@login_required
def kartu_kontrol_armada(request):
    """Halaman khusus riwayat service per mobil"""
    armada_list = Armada.objects.all()
    selected_armada_id = request.GET.get('armada_id')
    
    logs = []
    selected_armada = None
    
    if selected_armada_id:
        selected_armada = get_object_or_404(Armada, pk=selected_armada_id)
        
        # Filter: Hanya kategori ARMADA dan ID Mobil yang dipilih
        logs = BiayaOperasional.objects.filter(
            kategori_utama='ARMADA',
            armada_id=selected_armada_id
        ).order_by('-tanggal')

    return render(request, 'keuangan/kartu_kontrol.html', {
        'armada_list': armada_list,
        'selected_armada': selected_armada,
        'logs': logs
    })


# ==========================================
# 5. API AJAX (ANTI FRAUD / HELPER)
# ==========================================

@login_required
def get_armada_history(request):
    """
    API untuk mengambil 5 riwayat terakhir via AJAX.
    Digunakan di form ops_create untuk mencegah double input service.
    """
    armada_id = request.GET.get('armada_id')
    if not armada_id:
        return JsonResponse({'error': 'No ID'}, status=400)

    # Ambil 5 pengeluaran terakhir mobil ini
    history = BiayaOperasional.objects.filter(
        kategori_utama='ARMADA', 
        armada_id=armada_id
    ).order_by('-tanggal')[:5]
    
    data = []
    for h in history:
        data.append({
            'tanggal': h.tanggal.strftime('%d/%m/%Y'),
            'kategori': h.get_jenis_biaya_display(), # Pakai display name (e.g. "Ganti Ban")
            'keterangan': h.description,             # Field baru: description
            'nominal': float(h.nominal),
            'status': h.status                       # Field baru: status
        })
    
    return JsonResponse({'history': data})