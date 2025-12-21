from django.urls import path
from . import views

urlpatterns = [
    # Invoice & Payment
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/pay/<int:invoice_id>/', views.payment_create, name='payment_create'),
    
    # Operasional
    path('operational/', views.ops_list, name='ops_list'),
    path('operational/add/', views.ops_create, name='ops_create'),
    path('operational/approve/<int:pk>/', views.ops_approve, name='ops_approve'),
    path('operational/delete/<int:pk>/', views.ops_delete, name='ops_delete'),  
    
    path('api/armada-history/', views.get_armada_history, name='api_armada_history'),
    
    path('kartu-kontrol/', views.kartu_kontrol_armada, name='kartu_kontrol'),
]