from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Sum
from core.models import Kios, KiosAllocation, FertilizerPrice
from .models import SalesOrder, Distribution, StockAdjustment
from .forms import DistributionForm, StockAdjustmentForm
from django.template.loader import get_template
from xhtml2pdf import pisa
from core.decorators import owner_required

# --- VIEW UTAMA ---
def distribution_create(request):
    if request.method == 'POST':
        form = DistributionForm(request.POST)
        if form.is_valid():
            dist = form.save()
            messages.success(request, f"Penyaluran Berhasil! Surat Jalan: {dist.surat_jalan_no}")
            return redirect('distribution_list') # Nanti kita arahkan ke list distribusi
    else:
        form = DistributionForm()

    return render(request, 'gudang/distribution_form.html', {'form': form})

# --- API HELPER (Untuk AJAX JavaScript) ---
def get_kios_info(request):
    """
    API ini dipanggil saat Admin memilih Kios di dropdown.
    Mengembalikan data: Alamat, PIC, Sisa Kuota Kios, & Sisa Kuota Kecamatan.
    """
    kios_id = request.GET.get('kios_id')
    
    try:
        kios = Kios.objects.get(id=kios_id)
        
        # Hitung Kuota per Jenis
        # Format return: { 'NPK': {'kios': 10, 'district': 50}, 'UREA': ... }
        allocations = {}
        for f_type in ['NPK', 'UREA']:
            # 1. Kuota Kios Ini
            try:
                kios_alloc = KiosAllocation.objects.get(kios=kios, fertilizer_type=f_type, year=2025) # Harusnya dinamis tahunnya
                k_rem = kios_alloc.quota_remaining
            except KiosAllocation.DoesNotExist:
                k_rem = 0
            
            # 2. Kuota Satu Kecamatan (Untuk Fluid Allocation)
            d_rem = KiosAllocation.objects.filter(
                kios__district=kios.district,
                fertilizer_type=f_type,
                year=2025
            ).aggregate(Sum('quota_remaining'))['quota_remaining__sum'] or 0
            
            allocations[f_type] = {
                'kios_remaining': float(k_rem),
                'district_remaining': float(d_rem)
            }

        data = {
            'address': kios.address,
            'district': kios.district,
            'pic': kios.pic_name,
            'allocations': allocations
        }
        return JsonResponse(data)
        
    except Kios.DoesNotExist:
        return JsonResponse({'error': 'Kios not found'}, status=404)

def get_so_info(request):
    """
    API untuk mengambil data stok & jenis pupuk dari SO yang dipilih
    """
    so_id = request.GET.get('so_id')
    try:
        so = SalesOrder.objects.get(id=so_id)
        return JsonResponse({
            'fertilizer_type': so.fertilizer_type,
            'current_stock': float(so.tonnage_current)
        })
    except SalesOrder.DoesNotExist:
        return JsonResponse({'error': 'SO not found'}, status=404)
    
# --- LIST PENYALURAN (History) ---
def distribution_list(request):
    dist_data = Distribution.objects.all().select_related('kios', 'sales_order', 'armada').order_by('-transaction_date')
    return render(request, 'gudang/distribution_list.html', {'dist_data': dist_data})

# --- PDF GENERATOR ---
def print_document(request, pk, doc_type):
    """
    doc_type: 'sj' (Surat Jalan) atau 'inv' (Invoice)
    """
    dist = Distribution.objects.get(pk=pk)
    
    # Ambil Harga Master saat ini (Sesuai Jenis Pupuk SO)
    # Note: Idealnya harga disimpan di tabel Invoice, tapi untuk MVP kita ambil Master Harga
    try:
        price_obj = FertilizerPrice.objects.get(fertilizer_type=dist.sales_order.fertilizer_type)
        price_per_ton = price_obj.price_sell
    except FertilizerPrice.DoesNotExist:
        price_per_ton = 0

    total_price = dist.tonnage_sent * price_per_ton

    context = {
        'dist': dist,
        'price_per_ton': price_per_ton,
        'total_price': total_price,
        'doc_type': doc_type,
        'company': {
            'name': 'CV SEMBADA TANI',
            'address': 'Jl. Raya Pertanian No. 1, Semarang',
            'phone': '(024) 12345678'
        }
    }

    # Pilih Template HTML berdasarkan tipe dokumen
    if doc_type == 'sj':
        template_path = 'gudang/pdf_surat_jalan.html'
        filename = f"SJ_{dist.surat_jalan_no.replace('/', '-')}.pdf"
    else:
        template_path = 'gudang/pdf_invoice.html'
        filename = f"INV_{dist.surat_jalan_no.replace('/', '-')}.pdf"

    # Render HTML ke PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"' # 'inline' agar terbuka di browser, 'attachment' untuk auto-download

    template = get_template(template_path)
    html = template.render(context)
    
    # Create PDF
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

@owner_required # Security Layer: Hanya Owner/Superuser
def stock_opname(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            adjustment = form.save(commit=False)
            adjustment.executor = request.user # Auto-detect siapa yang login
            
            try:
                adjustment.save() # Trigger logic atomic transaction di models.py
                messages.success(request, f"✅ Stock Opname Berhasil. Stok SO {adjustment.sales_order.so_code} kini menjadi {adjustment.actual_stock} Ton.")
                return redirect('dashboard') # Atau redirect ke log list
            except Exception as e:
                messages.error(request, f"Terjadi Kesalahan Sistem: {e}")
    else:
        form = StockAdjustmentForm()

    return render(request, 'gudang/stock_opname.html', {'form': form})