from django.urls import path
from django.conf import settings
# from django.conf.urls.static import static

from . import views


urlpatterns = [
    # path("populate-instances", views.test_populate_instances),
    # path("", views.query),
    path(
        "<str:case>/studies/<str:study>/series/<str:series>/instances/<str:instance>",
        views.retrieve_instance,
    ),
    path(
        "<str:case>/studies/<str:study>/series/<str:series>/instances/<str:instance>/frames/<int:frame>",
        views.retrieve_instance,
    ),
    path("<str:case>/studies/<str:study>/metadata", views.study_metadata),
    path("<str:case>/studies/<str:study>/series/<str:series>/metadata", views.series_metadata),
    path(
        "<str:case>/studies/<str:study>/series/<str:series>/instances/<str:instance>/metadata",
        views.instance_metadata,
    ),
]
