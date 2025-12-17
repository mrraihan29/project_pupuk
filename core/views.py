from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Kios
from .forms import KiosForm, KiosAllocationFormSet

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

# --- DASHBOARD (View Lama) ---
def dashboard(request):
    return render(request, 'dashboard.html')