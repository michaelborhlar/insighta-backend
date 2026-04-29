from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "status": "error",
            "message": _extract_message(response.data),
        }
    return response


def _extract_message(data):
    if isinstance(data, dict):
        for key in ("detail", "message", "non_field_errors"):
            if key in data:
                val = data[key]
                if hasattr(val, "string"):
                    return str(val)
                if isinstance(val, list):
                    return str(val[0])
                return str(val)
        # Return first value found
        first = next(iter(data.values()), "An error occurred")
        if isinstance(first, list):
            return str(first[0])
        return str(first)
    if isinstance(data, list):
        return str(data[0])
    return str(data)
