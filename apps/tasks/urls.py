from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('create/', views.task_create, name='task_create'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
    path('<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('<int:pk>/accept/', views.task_accept, name='task_accept'),
    path('<int:pk>/complete/', views.task_complete, name='task_complete'),
    path('api/update-location/', views.update_location, name='update_location'),
    path('api/geojson/', views.tasks_geojson, name='tasks_geojson'),
]
