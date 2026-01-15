from django.urls import path
from . import views

urlpatterns = [
    # ==========================
    # 1. PENEBUSAN (SO / VIRTUAL STOCK)
    # ==========================
    path('so/', views.so_list, name='so_list'),
    path('so/create/', views.so_create, name='so_create'),

    # ==========================
    # 2. TRANSFER (TARIK STOK KE GUDANG)
    # ==========================
    path('transfer/', views.transfer_list, name='transfer_list'),
    path('transfer/create/', views.transfer_create, name='transfer_create'),

    # ==========================
    # 3. DISTRIBUSI (SURAT JALAN)
    # ==========================
    path('distribution/', views.distribution_list, name='distribution_list'),
    path('distribution/create/', views.distribution_create, name='distribution_create'),
    path('distribution/<int:pk>/print/', views.print_surat_jalan, name='print_surat_jalan'),
    
    # ==========================
    # 4. MONITORING STOK (LEDGER)
    # ==========================
    path('stock-card/', views.stock_card_list, name='stock_card_list'),
    path('stock-card/export/', views.stock_card_export_physical, name='stock_card_export_physical'),
    path('opname/', views.stock_opname, name='stock_opname'),

    # ==========================
    # 5. CATATAN ORDER
    # ==========================
    path('order-notes/', views.order_note_list, name='order_note_list'),
    path('order-notes/create/', views.order_note_create, name='order_note_create'),
    path('order-notes/<int:pk>/complete/', views.order_note_complete, name='order_note_complete'),
]