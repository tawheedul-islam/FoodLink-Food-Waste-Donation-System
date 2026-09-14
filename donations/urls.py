from django.urls import path
from . import views

urlpatterns = [
    path('', views.donation_list, name='donation_list'),
    path('create/', views.donation_create, name='donation_create'),
    path('<int:pk>/', views.donation_detail, name='donation_detail'),
]