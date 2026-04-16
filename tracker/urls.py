from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('friends/', views.friends_list, name='friends_list'),
    path('friends/delete/<int:friend_id>/', views.delete_friend, name='delete_friend'),

    path('groups/', views.groups_list, name='groups_list'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/members/', views.group_members_api, name='group_members_api'),
    path('groups/delete/<int:group_id>/', views.delete_group, name='delete_group'),

    path('split-expense/', views.split_expense, name='split_expense'),
    path('settlements/', views.settlements, name='settlements'),
]