from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('donations/', include('donations.urls')),
    path('requests/', include('requests_app.urls')),
]