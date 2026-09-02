from django.urls import path

from . import views

urlpatterns = [
    path(
        'projects/<int:project_id>/cycles/<int:cycle_id>/retro/create/',
        views.create_retro,
        name='create_retro',
    ),
    path('retros/<int:retro_id>/advance/', views.advance, name='advance_retro'),
    path('retros/<int:retro_id>/state', views.state, name='retro_state'),
]
