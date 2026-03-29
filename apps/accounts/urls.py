from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    delete_account,
    pending_verification,
    verify_coordinators,
    verify_coordinator,
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
]
