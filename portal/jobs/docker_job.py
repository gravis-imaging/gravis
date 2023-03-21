from .work_job import WorkJobView
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob

import portal.jobs.dicomset_utils as dicomset_utils
from loguru import logger
from pathlib import Path
import os
from uuid import uuid4
import docker

from django.conf import settings

import portal.jobs.dicomset_utils as dicomset_utils
from portal.models import Case, ProcessingJob
from common.constants import DockerReturnCodes


class DockerJob(WorkJobView):
    type = "DOCKER"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        do_docker_job(job)

    

def do_docker_job(job):
    # Run the container and handle errors of running the container
    input_folder = job.case.case_location + "/input/"

    try:
        docker_client = docker.from_env()
        job.status = "Processing"
        job.save()
        job_id = job.id
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
            GRAVIS_MIP_FULL_ROTATION=1, # This is True/False, need to pass 0 or 1 otherwise everything is converted to True.
            GRAVIS_NUM_BOTTOM_SLICES=20,
            DOCKER_RETURN_CODES=DockerReturnCodes.toDict(),
        )

        Path(output_folder).mkdir(parents=True, exist_ok=False)
    except Exception as e:
        raise Exception(f"Exception setting up job parameters for {input_folder}")

    logger.info(":::Docker job begin:::")
    logger.info(
        {
            "docker_tag": docker_tag,
            "volumes": volumes,
            "environment": environment,
        }
    )
    container = None
    try:
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
            raise Exception(f"Error while running container {docker_tag} - exit code {exit_code}. Value {DockerReturnCodes(exit_code).name}.")
    except docker.errors.APIError as e:
        # Something really serious happened
        raise Exception(
            f"API error while trying to run Docker container, tag: {docker_tag}"
        )  # handle_error
    except docker.errors.ImageNotFound as e:
        raise Exception(f"Error running docker container. Image for tag {docker_tag} not found.")
    except Exception as e:
        raise Exception(f"Unknown error running docker container.")
    finally:
        if container is not None:
            # Remove the container now to avoid that the drive gets full
            container.remove()
            
    try:
        subfolders = [ f.path for f in os.scandir(output_folder) if f.is_dir() ]
        for folder in subfolders:
            dicomset_utils.register( folder, job.case, "Processed", job_id)

        job.status = "Success"
        job.save()
    except Exception as e:
        raise Exception(
            f"Error creating output DICOMSet for {input_folder} for case {job.case}."
        )  # handle_error
