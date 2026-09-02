"""Application configuration, read from the environment.

The API key never lives in the source tree. The application reads it from an
environment variable at request time and only ever reports whether a key is
configured. The value itself is never returned by any endpoint and never
written to a log, so the configured state can be checked from a CI log or from
a browser without leaking anything.
"""

import os

# The name of the environment variable the key is read from. The same name is
# used by the GitHub Actions secret, so the workflow only has to map the secret
# onto this variable.
API_KEY_ENV = "OPENAI_API_KEY"


def api_key_configured() -> bool:
    """Return True when a non-empty API key is present in the environment.

    The environment is read on every call rather than once at import time, so
    the process picks up a key that was set after startup, and so the tests can
    set and unset it without reloading the module.
    """
    return bool(os.environ.get(API_KEY_ENV, "").strip())
