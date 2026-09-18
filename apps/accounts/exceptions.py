from rest_framework.views import exception_handler
from rest_framework.response import Response


def format_error_message(data) -> str:
    """
    Recursively formats any DRF error data structure (dict, list, string)
    into a clean, unified human-readable error string.
    """
    if isinstance(data, str):
        return data

    if isinstance(data, (list, tuple)):
        if not data:
            return "An error occurred."
        # If it's a list, take the first error or join them
        messages = [format_error_message(item) for item in data]
        return messages[0] if len(messages) == 1 else " | ".join(messages)

    if isinstance(data, dict):
        if "error" in data:
            return format_error_message(data["error"])
        if "detail" in data:
            return format_error_message(data["detail"])
        if "non_field_errors" in data:
            return format_error_message(data["non_field_errors"])
        if "message" in data and len(data) == 1:
            return format_error_message(data["message"])

        # Format field errors: e.g. "email: This field is required."
        parts = []
        for key, value in data.items():
            field_err = format_error_message(value)
            if key in ("non_field_errors", "detail", "__all__"):
                parts.append(field_err)
            else:
                parts.append(f"{key}: {field_err}")
        return " | ".join(parts) if parts else "An error occurred."

    return str(data)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that guarantees all API errors follow
    the unified format: {"error": "<details>", "detail": "<details>"}
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_message = format_error_message(response.data)
        response.data = {"error": error_message, "detail": error_message}

    return response

