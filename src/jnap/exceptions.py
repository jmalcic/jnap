"""Exceptions for the JNAP client."""


class JNAPError(Exception):
    """Raised when the JNAP API returns an unexpected response."""


class JNAPUnknownActionError(JNAPError):
    """Raised when the JNAP action is not recognised by the device."""


class JNAPUnauthorizedError(JNAPError):
    """Raised when JNAP authentication fails."""


class JNAPInvalidInputError(JNAPError):
    """Raised when JNAP request input is rejected by the device."""
