
from shlex import split
from pathlib import Path

from django.conf import settings

from portal.models import ProcessingJob
from portal.jobs.work_job import WorkJobView

from subprocess import CalledProcessError, check_output, STDOUT
class SendFindingsJob(WorkJobView):
    type="SEND_FINDINGS"

    DCMSEND_ERROR_CODES = {
        1: "EXITCODE_COMMANDLINE_SYNTAX_ERROR",
        21: "EXITCODE_NO_INPUT_FILES",
        22: "EXITCODE_INVALID_INPUT_FILE",
        23: "EXITCODE_NO_VALID_INPUT_FILES",
        43: "EXITCODE_CANNOT_WRITE_REPORT_FILE",
        60: "EXITCODE_CANNOT_INITIALIZE_NETWORK",   
        61: "EXITCODE_CANNOT_NEGOTIATE_ASSOCIATION",
        62: "EXITCODE_CANNOT_SEND_REQUEST",
        65: "EXITCODE_CANNOT_ADD_PRESENTATION_CONTEXT",
    }
    @classmethod
    def get_command(cls, job, in_dicom):
        # params = job.parameters
        # target_ip = params["target_ip"]
        # target_port = params.get("target_port", 104)
        # target_aet_source = params.get("target_aet_source", "")
        # target_aet_target = params.get("target_aet_target", "")
        if not settings.DISPATCH_HOST:
            raise Exception()
        target_host = settings.DISPATCH_HOST
        target_port = settings.DISPATCH_PORT
        aet_source = settings.DISPATCH_AET_SOURCE or ""
        aet_target = settings.DISPATCH_AET_SOURCE or ""
        return split(
            f"""dcmsend {target_host} {target_port} {in_dicom} -aet {aet_source} -aec {aet_target} -nuc -to 60 """ # +crf {dcmsend_status_file}
        )
    @classmethod
    def do_job(cls, job: ProcessingJob):
        findings = job.case.findings.all()

        dicoms = [Path(finding.case.case_location) / finding.dicom_location for finding in findings]

        for dicom in dicoms:
            command = cls.get_command(job, dicom)
            print(" ".join(command))
            try:
                result = check_output(command, encoding="utf-8", stderr=STDOUT)
            except CalledProcessError as e:
                raise Exception(f"Exited with value {e.returncode}, {cls.DCMSEND_ERROR_CODES[e.returncode]}")
            else:
                print(result)

        return {}, []