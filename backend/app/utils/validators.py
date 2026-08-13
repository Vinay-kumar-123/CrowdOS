import re


def is_valid_object_id(id_str: str) -> bool:
    """
    Validates standard 24-character hexadecimal BSON ObjectId format.
    """
    return bool(re.match(r"^[0-9a-fA-F]{24}$", id_str)) if id_str else False
