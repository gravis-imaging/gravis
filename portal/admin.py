from django.contrib import admin

# Register your models here.
from portal.models import Case, ProcessingJob, DICOMSet, DICOMInstance

# admin.site.register(ImageJob)
# admin.site.register(DockerJob)
admin.site.register(Case)
admin.site.register(ProcessingJob)
admin.site.register(DICOMSet)
admin.site.register(DICOMInstance)
