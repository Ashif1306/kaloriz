from django.urls import path
from . import views

app_name = 'shipping'

urlpatterns = [
    # JSON API Endpoints
    path('districts/', views.get_districts, name='get_districts'),
    path('quotes/', views.get_shipping_quotes, name='get_quotes'),

    # Address Management
    path('address/add/', views.add_address, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    path('address/archive/<int:address_id>/', views.archive_address, name='archive_address'),
    path('address/set-default/<int:address_id>/', views.set_default_address, name='set_default_address'),
]
