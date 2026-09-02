from django.urls import path

from . import views

urlpatterns = [
    path('new/', views.create_project, name='create_project'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('<int:project_id>/rotate/', views.rotate_join_link, name='rotate_join_link'),
    path('join/<uuid:token>/', views.join_project, name='join_project'),
]
