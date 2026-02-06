from django.urls import path
from . import views

urlpatterns = [
    # KIOS URLs
    path('kios/', views.kios_list, name='kios_list'),
    path('kios/add/', views.kios_create, name='kios_create'),
    path('kios/edit/<int:pk>/', views.kios_update, name='kios_update'),
    path('kios/delete/<int:pk>/', views.kios_delete, name='kios_delete'),
    
    path('laporan/raport/', views.raport_kios, name='raport_kios'),
    
    path('armada/', views.armada_list, name='armada_list'),
    path('armada/add/', views.armada_create, name='armada_create'),
    path('armada/edit/<int:pk>/', views.armada_update, name='armada_update'),
    path('armada/delete/<int:pk>/', views.armada_delete, name='armada_delete'),
    
    path('master/pupuk/', views.jenis_pupuk_list, name='jenis_pupuk_list'),
    path('master/pupuk/<int:pk>/edit/', views.jenis_pupuk_edit, name='jenis_pupuk_edit'),
    path('master/pupuk/<int:pk>/delete/', views.jenis_pupuk_delete, name='jenis_pupuk_delete'),
    path('master/harga/', views.master_harga, name='master_harga'),       # Untuk Menu Master Harga
        path('master-data-pupuk/', views.master_data_pupuk, name='master_data_pupuk'),
    path('laporan/keuangan/', views.laporan_keuangan, name='laporan_keuangan'), # Untuk Menu Laba Rugi

    # Setup (admin/staff only)
    path('setup/company-profile/', views.setup_company_profile, name='setup_company_profile'),
    path('setup/kabupaten/', views.setup_kabupaten, name='setup_kabupaten'),
    path('setup/kabupaten/<int:pk>/edit/', views.setup_kabupaten_edit, name='setup_kabupaten_edit'),
    path('setup/kabupaten/<int:pk>/delete/', views.setup_kabupaten_delete, name='setup_kabupaten_delete'),
    path('setup/kecamatan/', views.setup_kecamatan, name='setup_kecamatan'),
    path('setup/kecamatan/<int:pk>/edit/', views.setup_kecamatan_edit, name='setup_kecamatan_edit'),
    path('setup/kecamatan/<int:pk>/delete/', views.setup_kecamatan_delete, name='setup_kecamatan_delete'),
    path('setup/users/', views.setup_users, name='setup_users'),
    path('setup/users/<int:user_id>/edit/', views.setup_user_edit, name='setup_user_edit'),
    path('setup/users/<int:user_id>/delete/', views.setup_user_delete, name='setup_user_delete'),
    path('setup/users/<int:user_id>/password/', views.setup_user_set_password, name='setup_user_set_password'),
]