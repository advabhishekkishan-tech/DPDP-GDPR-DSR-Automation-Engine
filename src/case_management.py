class RequestRegistry:
    """Minimal case registry for duplicate-request detection in the prototype."""

    def __init__(self):
        self._requests = {}

    def register(self, request_id: str, subject_email: str, request_type: str) -> bool:
        key = (subject_email.lower(), request_type)
        if key in self._requests:
            return False
        self._requests[key] = request_id
        return True

    def existing_request(self, subject_email: str, request_type: str) -> str | None:
        return self._requests.get((subject_email.lower(), request_type))
