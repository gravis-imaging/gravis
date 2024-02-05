from django.urls import include, path
# from .jobs import cine_generation
from . import views, endpoints, jobs

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("", views.index, name="index"),
    path('accounts/', include('registration.backends.admin_approval.urls')),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),
    path("user/", views.user, name="user"),
    path("config/", views.config, name="config"),
    path("media/<path:path>", views.serve_media),
    path("viewer/<str:case_id>", views.viewer, name="viewer"),
    path("viewer/<str:case_id>/info", views.case_info, name="viewer"),
    path("filebrowser/", views.file_browser, name="file_browser"),
    path("filebrowser/<path:path>", views.file_browser, name="file_browser"),
    *endpoints.urls,
    *jobs.urls,
    *staticfiles_urlpatterns()
]
