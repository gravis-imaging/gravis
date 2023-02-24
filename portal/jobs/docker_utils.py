# import logging
from loguru import logger
from pathlib import Path
import os
from uuid import uuid4
import docker

from django.conf import settings

import portal.jobs.dicom_set_utils as dicom_set_utils
from portal.models import Case, ProcessingJob
from common.constants import DockerReturnCodes


def do_docker_job(job_id):
    # TODO move docker stuff in a separate file.
    # Run the container and handle errors of running the container
    processing_success = True

    try:
        job: ProcessingJob = ProcessingJob.objects.get(id=job_id)
    except Exception as e:
        logger.exception(f"ProcessingJob with id {job_id} does not exist.")
        return False

    input_folder = job.case.case_location + "/input/"

    try:
        docker_client = docker.from_env()

        job.status = "Processing"
        job.save()
        docker_tag = job.docker_image

        # Volume for subtracted slices
        output_folder = job.case.case_location + "/processed/" + str(uuid4())

        volumes = {
            input_folder: {"bind": "/tmp/data/", "mode": "rw"},
            output_folder: {"bind": "/tmp/output/", "mode": "rw"},
        }

        # settings = {"n_slices": 20, "angle_step": 10, "full_rotation_flag": False}
        environment = dict(
            GRAVIS_IN_DIR="/tmp/data/",
            GRAVIS_OUT_DIR="/tmp/output/",
            GRAVIS_ANGLE_STEP=10,
            GRAVIS_MIP_FULL_ROTATION=0, # This is True/False, need to pass 0 or 1 otherwise everything is converted to True.
            GRAVIS_NUM_BOTTOM_SLICES=20,
            DOCKER_RETURN_CODES=DockerReturnCodes.toDict(),
        )

        Path(output_folder).mkdir(parents=True, exist_ok=False)
    except Exception as e:
        process_job_error(job_id, e)

        logger.exception(f"Exception setting up job parameters for {input_folder}")
        processing_success = False
    else:
        try:
            logger.info(":::Docker job begin:::")
            logger.info(
                {
                    "docker_tag": docker_tag,
                    "volumes": volumes,
                    "environment": environment,
                }
            )

            container = docker_client.containers.run(
                docker_tag,
                volumes=volumes,
                environment=environment,
                # user=f"{os.getuid()}:{os.getegid()}",
                # group_add=[os.getegid()],
                detach=True,
            )

            docker_result = container.wait()
            logger.info("DOCKER RESULTS: ", docker_result)

            logger.info(
                "=== MODULE OUTPUT - BEGIN ========================================"
            )
            if container.logs() is not None:
                logs = container.logs().decode("utf-8")
                logger.info(logs)
            logger.info(
                "=== MODULE OUTPUT - END =========================================="
            )

            # Check if the processing was successful (i.e., container returned exit code 0)
            exit_code = docker_result.get("StatusCode")
            if exit_code != 0:
                error_description = f"Error while running container {docker_tag} - exit code {exit_code}. Value {DockerReturnCodes(exit_code).name}."
                process_job_error(job_id, error_description)
                logger.error(error_description)  # handle_error
                processing_success = False

            # Remove the container now to avoid that the drive gets full
            container.remove()

        except docker.errors.APIError as e:
            # Something really serious happened
            process_job_error(job_id, e)
            logger.error(
                f"API error while trying to run Docker container, tag: {docker_tag}"
            )  # handle_error
            processing_success = False

        except docker.errors.ImageNotFound as e:
            process_job_error(job_id, e)
            logger.error(
                f"Error running docker container. Image for tag {docker_tag} not found."
            )  # handle_error
            processing_success = False

        except Exception as e:
            process_job_error(job_id, e)
            logger.exception(
                f"Error running docker container. Image for tag {docker_tag} not found."
            )  # handle_error
            processing_success = False

    if not processing_success:
        raise Exception("Processing failed.")

    # TODO figure out sub/mip from dicom tags
    job.complete = True
    try:
        subfolders = [ f.path for f in os.scandir(output_folder) if f.is_dir() ]
        for folder in subfolders:
            register_dicom_set_success, error = dicom_set_utils.register(
                folder, job.case, "Processed", job_id
            )
            if not register_dicom_set_success:
                process_job_error(job_id, error)
                return False


        # register_dicom_set_success, error = dicom_set_utils.register(
        #     output_folder + "/mip", job.case, "Processed", "MIP", job_id
        # )
        # if not register_dicom_set_success:
        #     process_job_error(job_id, error)
        #     return False
        job.status = "Success"
        # job.dicom_set = dicom_set
        job.case.status = Case.CaseStatus.READY
        job.case.save()
        job.save()
    except Exception as e:
        process_job_error(job_id, e)
        logger.error(
            f"Error creating output DICOMSet for {input_folder} for case {job.case}."
        )  # handle_error
        processing_success = False

    if not processing_success:
        raise Exception("Processing failed.")

    return processing_success


def process_job_error(job_id, error_description):
    logger.error(error_description)
    try:
        job: ProcessingJob = ProcessingJob.objects.get(id=job_id)
    except Exception as e:
        logger.exception(f"ProcessingJob with id {job_id} does not exist.")
        return False
    folder_name = Path(job.case.case_location).name # "foo/bar" -> bar, "foo/bar/" => bar
    print("ERROR FOLDER!!!: ", folder_name)
    dicom_set_utils.move_files(
        Path(job.case.case_location), Path(settings.ERROR_FOLDER) / folder_name
    )
    job.case.status = Case.CaseStatus.ERROR
    job.case.save()
    job.status = "Fail"
    job.error_description = error_description
    job.save()
