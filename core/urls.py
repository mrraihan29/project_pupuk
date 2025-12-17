from django.urls import path
from . import views

urlpatterns = [
    # KIOS URLs
    path('kios/', views.kios_list, name='kios_list'),
    path('kios/add/', views.kios_create, name='kios_create'),
    path('kios/edit/<int:pk>/', views.kios_update, name='kios_update'),
    path('kios/delete/<int:pk>/', views.kios_delete, name='kios_delete'),
]