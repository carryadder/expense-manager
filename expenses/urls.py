from django.urls import path

from . import views

urlpatterns = [
    path('', views.group_list, name='group_list'),
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    path('groups/<int:pk>/invite/', views.group_invite, name='group_invite'),
    path('groups/<int:pk>/members/<int:member_pk>/remove/', views.member_remove, name='member_remove'),
    path('groups/<int:pk>/add-expense/', views.expense_create, name='expense_create'),
    path('join/<str:code>/', views.group_join, name='group_join'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('members/', views.member_list, name='member_list'),
    path('members/<int:pk>/delete/', views.member_delete, name='member_delete'),
    path('settings/', views.settings_view, name='settings'),
    path('signup/', views.signup, name='signup'),
]
