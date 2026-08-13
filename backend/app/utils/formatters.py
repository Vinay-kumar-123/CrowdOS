def format_api_response(data=None, message="Success", status="success"):
    """
    Format standard API response dictionary.
    """
    return {
        "status": status,
        "message": message,
        "data": data,
    }
