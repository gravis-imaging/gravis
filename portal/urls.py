from django.urls import path

from . import views, rqjobs, grasp_endpoints

from django.conf import settings
from django.conf.urls.static import static

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("", views.index, name="index"),
    # path("docker_job/", views.docker_job),
    # path("work_test/", views.work_queue_test),
    # path("work_status/<int:id>/", views.work_status),
    path("viewer/<str:case>", views.viewer, name="viewer"),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),
    path("config/", views.config, name="config"),
    path("user/", views.user, name="user"),
    path("media/<path:path>", views.serve_media),
    path("api/grasp/data/<str:case>/<str:study>", grasp_endpoints.grasp_metadata),
    path("api/grasp/preview/<str:case>/<str:view>/<int:index>", grasp_endpoints.preview_data),

    *rqjobs.urls,
    *staticfiles_urlpatterns()
]
