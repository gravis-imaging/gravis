import uuid


def generate_folder_name() -> str:
    new_uuid = str(uuid.uuid4())
    return new_uuid
