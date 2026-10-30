"""Public errors deliberately exclude credentials and raw HTTP request data."""


class BoldstoneError(Exception):
    exit_code = 2

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


class Blocked(BoldstoneError):
    exit_code = 3


class Partial(BoldstoneError):
    exit_code = 4


class RemoteError(BoldstoneError):
    exit_code = 5

    def __init__(self, kind, message=None, *, request_id=None, retry_after=None, details=None):
        super().__init__(message or f"Dropbox read failed: {kind}", details=details)
        self.kind = kind
        self.request_id = request_id
        self.retry_after = retry_after

    def public(self):
        return {
            "kind": self.kind,
            "message": str(self),
            "request_id": self.request_id,
            "retry_after": self.retry_after,
            **self.details,
        }


class IntegrityError(BoldstoneError):
    exit_code = 7
