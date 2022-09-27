from django.urls import path

from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.index, name="index"),
    path("docker_job/", views.docker_job),
    path("work_test/", views.work_queue_test),
    path("watch_incoming/", views.watch_incoming),
    path("work_status/<int:id>/", views.work_status),
    path("viewer/<str:case>", views.viewer, name="viewer"),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),
    path("config/", views.config, name="config"),
    path("user/", views.user, name="user"),
    path("media/<path:path>", views.serve_file),
    *static(settings.STATIC_URL, document_root="portal/static/"),
]
