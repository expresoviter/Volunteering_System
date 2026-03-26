from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('volunteers/', include('apps.volunteers.urls')),
    path('', RedirectView.as_view(url='/tasks/', permanent=False)),
]
