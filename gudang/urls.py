from django.urls import path
from . import views

urlpatterns = [
    path('distribution/add/', views.distribution_create, name='distribution_create'),
    
    # List Distribusi
    path('distribution/list/', views.distribution_list, name='distribution_list'),
    path('distribution/print/<int:pk>/<str:doc_type>/', views.print_document, name='print_document'),
    
    # API Endpoints (Dipanggil JS)
    path('api/get-kios-info/', views.get_kios_info, name='api_get_kios_info'),
    path('api/get-so-info/', views.get_so_info, name='api_get_so_info'),
    path('api/so-details/', views.get_so_details, name='get_so_details'),
    
    # Stock Opname
    path('stock-opname/', views.stock_opname, name='stock_opname'),
    
    # Sales Order (Penebusan)
    path('penebusan/', views.so_list, name='so_list'),
    path('penebusan/add/', views.so_create, name='so_create'),
    path('kartu-stok/', views.stock_card_list, name='stock_card_list'),
    
]