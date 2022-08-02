from django.urls import path

from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('work_test/', views.work_queue_test),
    path('work_status/<int:id>/', views.work_status),
    path('login/', views.login_request, name='login'),
    path('logout/', views.logout_request, name='logout'),
]+ static(settings.MEDIA_URL, document_root=settings.DATA_FOLDER)