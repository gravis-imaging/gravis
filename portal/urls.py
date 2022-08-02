from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('work_test/', views.work_queue_test),
    path('login/', views.login_request, name='login'),
    path('logout/', views.logout_request, name='logout'),
]
