from django.shortcuts import redirect
from django.contrib import messages

def owner_required(view_func):
    def wrapper_func(request, *args, **kwargs):
        # Cek apakah user masuk grup 'Owner' atau dia Superuser
        if request.user.is_superuser or request.user.groups.filter(name='Owner').exists():
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Akses Ditolak! Halaman ini khusus Owner.")
            return redirect('dashboard')
    return wrapper_func