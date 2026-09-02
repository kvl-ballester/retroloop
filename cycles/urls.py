from django.urls import path

from . import views

urlpatterns = [
    path(
        'projects/<int:project_id>/cycles/new/',
        views.create_cycle,
        name='create_cycle',
    ),
    path(
        'projects/<int:project_id>/cycles/<int:cycle_id>/close/',
        views.close_cycle,
        name='close_cycle',
    ),
]
