from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('verification/request/', views.verification_request_view, name='verification_request'),
    path('organizations/', views.organization_list, name='organizations'),
    path('organizations/<int:pk>/', views.organization_detail, name='organization_detail'),
    path('organizations/<int:pk>/invite/', views.invite_organization_member, name='organization_invite'),
    path('organizations/invitations/<int:pk>/<str:action>/', views.respond_to_organization_invitation, name='organization_invitation_response'),
    path('organizations/<int:pk>/members/<int:user_id>/remove/', views.remove_organization_member, name='organization_remove_member'),
]