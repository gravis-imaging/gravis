from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from portal.models import Case, ProcessingJob, DICOMSet, DICOMInstance, Finding, UserProfile, ShadowCase


class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'UserProfile'
    fk_name = 'user'


class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, )

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)


class DicomSetInline(admin.TabularInline):
    model = DICOMSet
    # exclude = ["origin","expires_at","created_at"]
    fields = ["id", "type", "processing_job","created_at"]
    readonly_fields = ["id","type","processing_job","created_at"]
    can_delete = False
    show_change_link = True
    def get_extra(self, request, obj=None, **kwargs):
        return 0
class CaseInline(admin.TabularInline):
    model = Case
    fields = [ "patient_name", "mrn", "acc" ]
    readonly_fields = ["patient_name", "mrn", "acc"]
    can_delete = False
    show_change_link = True
    def get_extra(self, request, obj=None, **kwargs):
        return 0
    
class FindingInline(admin.TabularInline):
    model = Finding
    can_delete = False
    show_change_link = True
    exclude = ["dicom_set"]
    readonly_fields = ["created_by", "created_at","name","file_location","dicom_location", "data"]
    extra = 0
class CaseAdmin(admin.ModelAdmin):
    inlines = [
        DicomSetInline, FindingInline
    ]
    list_display = ["id", "patient_name", "mrn", "acc", "case_type", "case_location"]
class ProcessingJobInline(admin.TabularInline):
    model = ProcessingJob

class ProcessingJobAdmin(admin.ModelAdmin):
    inlines = [
        DicomSetInline
    ]
    fields = ["category","case","dicom_set","status","docker_image","parameters","json_result","rq_id"]
    readonly_fields = ["dicom_set","case","rq_id"]
    
    list_display = ["id", "category", "case_info","status"]

    @admin.display(description="Case")
    def case_info(self,obj):
        return f"{obj.case.id}; {obj.case.patient_name}" if obj.case else "-"

class FindingAdmin(admin.ModelAdmin):
    # form = DICOMSetAdminForm
    fields = ["dicom_set","case","created_by", "created_at","name", "file_location","dicom_location","data"]
    readonly_fields = ["dicom_set","case"]
    list_display = ["id", "case_info","created_at"]

    @admin.display(description="Case")
    def case_info(self,obj):
        return f"{obj.case.id}; {obj.case.patient_name}" if obj.case else "-"

class DICOMSetAdmin(admin.ModelAdmin):
    # form = DICOMSetAdminForm
    fields = ["type", "case", "set_location", "created_at","origin", "expires_at","is_volume","frame_of_reference", "image_orientation_patient", "image_orientation_calc","image_orientation_calc_inv"]
    readonly_fields = ["case", "created_at","processing_job", "image_orientation_patient", "image_orientation_calc","image_orientation_calc_inv"]
    list_display = ["id", "case_info", "type"]

    @admin.display(description="Case")
    def case_info(self,obj):
        return f"{obj.case.id}; {obj.case.patient_name}"

class ShadowAdmin(admin.ModelAdmin):
    inlines = [ CaseInline ]
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Case, CaseAdmin)
admin.site.register(ProcessingJob, ProcessingJobAdmin)
admin.site.register(DICOMSet,DICOMSetAdmin)
admin.site.register(DICOMInstance)
admin.site.register(Finding, FindingAdmin)
admin.site.register(ShadowCase, ShadowAdmin)
