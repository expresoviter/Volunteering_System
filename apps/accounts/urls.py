from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    delete_account,
    pending_verification,
    verify_coordinators,
    verify_coordinator,
    decline_coordinator,
    coordinator_profile,
    coordinator_org_create,
    coordinator_org_join,
    coordinator_org_leave,
    admin_dashboard,
    admin_users,
    admin_organizations,
    admin_verify_organization,
    admin_verify_coordinator,
    admin_delete_user,
    admin_delete_organization,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('delete/', delete_account, name='delete_account'),
    path('pending-verification/', pending_verification, name='pending_verification'),
    path('verify-coordinators/', verify_coordinators, name='verify_coordinators'),
    path('verify-coordinator/<int:pk>/', verify_coordinator, name='verify_coordinator'),
    path('decline-coordinator/<int:pk>/', decline_coordinator, name='decline_coordinator'),
    path('coordinator/profile/',    coordinator_profile,     name='coordinator_profile'),
    path('coordinator/org/create/', coordinator_org_create,  name='coordinator_org_create'),
    path('coordinator/org/join/',   coordinator_org_join,    name='coordinator_org_join'),
    path('coordinator/org/leave/',  coordinator_org_leave,   name='coordinator_org_leave'),
    # Панель адміністратора
    path('admin-panel/',                              admin_dashboard,           name='admin_dashboard'),
    path('admin-panel/users/',                        admin_users,               name='admin_users'),
    path('admin-panel/organizations/',                admin_organizations,       name='admin_organizations'),
    path('admin-panel/verify-org/<int:pk>/',          admin_verify_organization, name='admin_verify_organization'),
    path('admin-panel/verify-coordinator/<int:pk>/',  admin_verify_coordinator,  name='admin_verify_coordinator'),
    path('admin-panel/delete-user/<int:pk>/',         admin_delete_user,         name='admin_delete_user'),
    path('admin-panel/delete-org/<int:pk>/',          admin_delete_organization, name='admin_delete_organization'),
]
