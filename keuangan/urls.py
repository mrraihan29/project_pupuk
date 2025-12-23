from django.urls import path
from . import views

urlpatterns = [
    # INVOICE & PAYMENT
    path('invoice/', views.invoice_list, name='invoice_list'),
    path('invoice/<int:pk>/pay/', views.payment_create, name='payment_create'),
    path('invoice/<int:pk>/print/', views.print_invoice, name='print_invoice'),

    # BIAYA OPERASIONAL (LIST & CREATE)
    path('biaya/', views.ops_list, name='ops_list'),
    path('biaya/create/', views.ops_create, name='ops_create'),
    
    # ACTION OWNER (APPROVE & DELETE) - FITUR INI TIDAK HILANG!
    path('biaya/<int:pk>/approve/', views.ops_approve, name='ops_approve'),
    path('biaya/<int:pk>/delete/', views.ops_delete, name='ops_delete'),

    # FITUR KHUSUS ARMADA
    path('kartu-kontrol/', views.kartu_kontrol_armada, name='kartu_kontrol'),
    path('api/armada-history/', views.get_armada_history, name='api_armada_history'),
]