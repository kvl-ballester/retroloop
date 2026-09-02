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
    path('cycles/<int:cycle_id>/feedback/', views.feedback_form, name='feedback'),
    path(
        'cycles/<int:cycle_id>/cards/<int:card_id>/edit/',
        views.edit_card,
        name='edit_card',
    ),
    path(
        'cycles/<int:cycle_id>/cards/<int:card_id>/delete/',
        views.delete_card,
        name='delete_card',
    ),
]
