from django.urls import path
# from .jobs import cine_generation
from . import views, grasp_endpoints, jobs
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from .rest import CaseView

urlpatterns = [
    path("", views.index, name="index"),
    path("browser/get_cases_all", views.browser_get_cases_all),
    path("browser/get_tags_all", views.browser_get_tags_all),
    path("browser/get_case_tags_and_all_tags/<str:case_id>", views.browser_get_case_tags_and_all_tags),
    path("browser/get_case/<str:case>", views.browser_get_case),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),

    # path("docker_job/", views.docker_job),
    # path("work_test/", views.work_queue_test),
    # path("work_status/<int:id>/", views.work_status),
    path("viewer/<str:case>", views.viewer, name="viewer"),
    path("config/", views.config, name="config"),
    path("user/", views.user, name="user"),
    path("user/settings", views.settings, name='settings'), 
    path("cases/", CaseView()),
    path("media/<path:path>", views.serve_media),
    path("update_case_tags/", views.update_case_tags),
    path("update_tags/", views.update_tags),

    path("api/case/<str:case>/dicom_set/<str:source_set>/timeseries",grasp_endpoints.timeseries_data),
    path("api/case/<str:case>/dicom_set/<str:source_set>/preview/<str:view>/<str:location>", grasp_endpoints.preview_urls),
    path("api/case/<str:case>/dicom_set/<str:source_set>/processed_results/<path:case_type>", grasp_endpoints.processed_results_urls),
    path("api/case/<str:case>/dicom_set/<str:source_set>/mip_metadata", grasp_endpoints.mip_metadata),
    path("api/case/<str:case>/dicom_set/<str:source_set>/processed_json/<str:category>", grasp_endpoints.processed_results_json),
    path("api/case/<str:case>/dicom_set/<str:dicom_set>/metadata", grasp_endpoints.case_metadata),
    path("api/case/<str:case>/dicom_set/<str:dicom_set>/study/<str:study>/metadata", grasp_endpoints.case_metadata),
    path("api/case/<str:case>/dicom_set/<str:source_set>/finding", grasp_endpoints.store_finding),
    path("api/case/<str:case>/dicom_set/<str:source_set>/finding/<int:finding_id>", grasp_endpoints.store_finding),
    path("api/case/<str:case>/sessions", grasp_endpoints.all_sessions),
    path("api/case/<str:case>/session", grasp_endpoints.handle_session),
    path("api/case/<str:case>/session/new", grasp_endpoints.new_session),
    path("api/case/<str:case>/session/<int:session_id>", grasp_endpoints.handle_session),
    *jobs.urls,
    *staticfiles_urlpatterns()
]
