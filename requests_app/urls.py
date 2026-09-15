from django.urls import path
from . import views

urlpatterns = [
    path('create/<int:pk>/', views.create_request, name='create_request'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('incoming/', views.incoming_requests, name='incoming_requests'),
    path('update/<int:pk>/<str:new_status>/', views.update_request_status, name='update_request_status'),
    path('cancel/<int:pk>/', views.cancel_request, name='cancel_request'),
]