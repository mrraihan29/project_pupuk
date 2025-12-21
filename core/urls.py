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
    
    path('master/harga/', views.master_harga, name='master_harga'),       # Untuk Menu Master Harga
    path('laporan/keuangan/', views.laporan_keuangan, name='laporan_keuangan'), # Untuk Menu Laba Rugi
]