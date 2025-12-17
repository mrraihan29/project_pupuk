from django.urls import path
from . import views

urlpatterns = [
    path('distribution/add/', views.distribution_create, name='distribution_create'),
    
    # API Endpoints (Dipanggil JS)
    path('api/get-kios-info/', views.get_kios_info, name='api_get_kios_info'),
    path('api/get-so-info/', views.get_so_info, name='api_get_so_info'),
]