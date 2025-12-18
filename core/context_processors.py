def access_controls(request):
    """
    Context Processor ini akan berjalan di SETIAP request.
    Tugasnya: Mengembalikan daftar nama Group milik user yang sedang login.
    Output: Variable 'user_groups' yang bisa dipakai di semua file HTML.
    """
    if request.user.is_authenticated:
        # Ambil daftar nama group user ini.
        # Contoh output: ['Owner', 'Staff Gudang']
        groups = list(request.user.groups.values_list('name', flat=True))
    else:
        groups = []

    return {
        'user_groups': groups
    }