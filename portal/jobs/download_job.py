import gzip
import shutil
import zipfile
from pathlib import Path
from zipfile import ZipInfo
from django.conf import settings
from .work_job import WorkJobView
from portal.models import ProcessingJob


class CaseDownloadJob(WorkJobView):
    type = "DOWNLOAD"
    job_timeout = 60 * 60 * 12  # 12 hours — large cases can contain thousands of files

    @classmethod
    def do_job(cls, job: ProcessingJob):
        case = job.case
        case_path = Path(case.case_location)
        include_cine = job.parameters.get("include_cine", False)

        downloads_dir = case_path / "downloads"
        downloads_dir.mkdir(exist_ok=True)

        # Required by WorkJobView._do_job which chmods this directory unconditionally
        (case_path / "processed").mkdir(exist_ok=True)

        zip_name = "case_{}_with_cine.zip".format(case.id) if include_cine else "case_{}.zip".format(case.id)
        zip_path = downloads_dir / zip_name

        dicom_sets = case.dicom_sets.all()
        if not include_cine:
            dicom_sets = dicom_sets.exclude(type__startswith="CINE")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            seen_paths = set()
            for dicom_set in dicom_sets:
                set_path = Path(dicom_set.set_location)
                for instance in dicom_set.instances.only("instance_location"):
                    abs_path = set_path / instance.instance_location
                    # handle .dcm.gz variant
                    if not abs_path.exists():
                        abs_path = Path(str(abs_path) + ".gz")
                    if abs_path.exists() and abs_path not in seen_paths:
                        seen_paths.add(abs_path)
                        arcname = abs_path.relative_to(case_path)
                        if abs_path.suffix == ".gz":
                            arcname = arcname.with_suffix("")  # strip .gz from archive name
                            info = ZipInfo(str(arcname))
                            with gzip.open(abs_path, "rb") as gz_in, zf.open(info, "w", force_zip64=True) as zip_out:
                                shutil.copyfileobj(gz_in, zip_out, length=1024 * 1024)
                        else:
                            zf.write(abs_path, arcname)

            # Include findings
            for finding in case.findings.all():
                for loc in [finding.file_location, finding.dicom_location]:
                    if not loc:
                        continue
                    abs_path = case_path / loc
                    if abs_path.exists() and abs_path not in seen_paths:
                        seen_paths.add(abs_path)
                        zf.write(abs_path, Path(loc))

        relative_path = str(zip_path.relative_to(Path(settings.DATA_FOLDER)))
        return ({"zip_path": relative_path, "include_cine": include_cine}, [])
