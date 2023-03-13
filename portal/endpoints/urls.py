from django.urls import path as url_path
from . import *

def path(url, *args):
    return url_path("api/case/<str:case>/"+url, *args)

urls = [
    path("dicom_set/<str:source_set>/timeseries",timeseries.timeseries_data),
    path("dicom_set/<str:source_set>/preview/<str:view>/<str:location>", case_data.preview_urls),
    path("dicom_set/<str:source_set>/processed_results/<path:case_type>", case_data.processed_results_urls),
    path("dicom_set/<str:source_set>/mip_metadata", case_data.mip_metadata),
    path("dicom_set/<str:source_set>/processed_json/<str:category>", case_data.processed_results_json),
    path("dicom_set/<str:dicom_set>/metadata", case_data.case_metadata),
    path("dicom_set/<str:dicom_set>/study/<str:study>/metadata", case_data.case_metadata),
    path("dicom_set/<str:source_set>/finding", findings.handle_finding),
    path("dicom_set/<str:source_set>/finding/<int:finding_id>", findings.handle_finding),
    path("sessions", sessions.all_sessions),
    path("session", sessions.handle_session),
    path("session/new", sessions.new_session),
    path("session/<int:session_id>", sessions.handle_session),

    path("", case_data.get_case),
    path("delete", case_data.delete_case),
    path("status/<str:new_status>", case_data.set_case_status),

    path("tags", tags.case_tags),
    path("tags/update", tags.update_case_tags),

    url_path("api/cases", case_data.all_cases),
    url_path("api/tags", tags.all_tags),
    url_path("api/tags/update", tags.update_tags),
]