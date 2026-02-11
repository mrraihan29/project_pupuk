from django.urls import path
from . import views

urlpatterns = [
    # INVOICE & PAYMENT
    path('invoice/', views.invoice_list, name='invoice_list'),
    path('invoice/<int:pk>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoice/<int:pk>/pay/', views.payment_create, name='payment_create'),
    path('invoice/<int:pk>/print/', views.print_invoice, name='print_invoice'),
    path('payment/<int:pk>/edit/', views.payment_edit, name='payment_edit'),
    path('payment/<int:pk>/void/', views.payment_void, name='payment_void'),

    # BIAYA OPERASIONAL (LIST, CREATE & EDIT)
    path('biaya/', views.ops_list, name='ops_list'),
    path('biaya/create/', views.ops_create, name='ops_create'),
    path('biaya/<int:pk>/edit/', views.ops_edit, name='ops_edit'),
    
    # ACTION OWNER (APPROVE, REJECT & DELETE) - FITUR INI TIDAK HILANG!
    path('biaya/<int:pk>/approve/', views.ops_approve, name='ops_approve'),
    path('biaya/<int:pk>/reject/', views.ops_reject, name='ops_reject'),
    path('biaya/<int:pk>/delete/', views.ops_delete, name='ops_delete'),

    # FITUR KHUSUS ARMADA
    path('kartu-kontrol/', views.kartu_kontrol_armada, name='kartu_kontrol'),
    path('api/armada-history/', views.get_armada_history, name='api_armada_history'),
]