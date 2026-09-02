# syntax=docker/dockerfile:1

# ============================================================================
# DEDIH 2.0 CI/CD course, demo Dockerfile
# ----------------------------------------------------------------------------
# The goal is not the smallest possible image, it is that the principles of a
# container build are visible:
#
#   1. multi-stage build:  the tools needed for installing do not end up in the
#                          shipped image
#   2. pinned base image:  the base image is a dependency too, one we did not
#                          write
#   3. non-root user:      the application does not run as root in the container
#   4. minimal copying:    only the application code goes in, not .git and not
#                          the tests
#
# Build from the repository root. The context and the location of the
# Dockerfile are two separate things:
#
#   docker build -f docker/Dockerfile -t dedih-demo:local .
#                ^ where the Dockerfile is              ^ the build context
#
# Run:
#
#   docker run --rm -p 8000:8000 dedih-demo:local
#
# The Swagger UI is then served at http://127.0.0.1:8000/docs.
# ============================================================================


# ----------------------------------------------------------------------------
# 1. STAGE: builder
# ----------------------------------------------------------------------------
# The dependencies are installed into a separate virtualenv here. This stage
# contains pip, the downloaded packages and everything else needed for the
# install, but only the finished virtualenv is carried over to the second
# stage.
#
# The base image version is pinned (3.11-slim-bookworm), not "latest". The
# logic of the supply chain block applies here as well: the base image is a
# dependency we did not write. In production the convention is to pin a digest
# instead of a tag (python:3.11-slim-bookworm@sha256:...), because a tag can be
# repointed and a digest cannot.
# ----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Only requirements.txt is copied in first. As long as this file does not
# change, Docker reuses the install layer and the build finishes in seconds. If
# the whole source tree were copied here, every small code change would trigger
# a full reinstall of every package.
COPY requirements.txt .

# This requirements.txt holds both the runtime packages (fastapi, uvicorn,
# pydantic) and the development tools (pytest, ruff), so the development tools
# end up in the image as well. A production project splits this into
# requirements.txt and requirements-dev.txt: smaller image, smaller attack
# surface.
#
# pip, setuptools and wheel are removed once the install is finished. The
# application does not need them, and they are not free to keep: pip carries a
# vendored copy of its own dependency tree, and the scanner reports the known
# vulnerabilities of that tree as part of our image, even though no line of
# requirements.txt can change them. Removing the installer also means an
# intruder who gets a shell in the container has no way to install anything.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip uninstall --yes pip setuptools wheel


# ----------------------------------------------------------------------------
# 2. STAGE: runtime
# ----------------------------------------------------------------------------
# This is the image that ships. It starts from a clean slate and receives only
# the finished virtualenv and the application code. The downloaded package
# files and the leftovers of the build are not present.
# ----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# PYTHONDONTWRITEBYTECODE: do not write .pyc files into the container
# PYTHONUNBUFFERED:        log output appears immediately, unbuffered
# PATH:                    the virtualenv becomes the default Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# The base image ships its own pip, setuptools and wheel in the system
# site-packages directory. The application runs from the virtualenv and never
# uses them, but the scanner still finds them and reports their known
# vulnerabilities, and an intruder who gets a shell in the container would find
# a working package installer. Removing them takes away both. The standard
# library is in a different directory and is left untouched.
RUN rm -rf /usr/local/lib/python3.11/site-packages/*

# Least privilege: a dedicated, unprivileged user. By default the container
# would run as root and a process that breaks out would start with root
# rights. This is the same principle as the permissions block of a workflow:
# only as much privilege as is actually needed.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# The finished virtualenv is carried over from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Only the application code goes in. No .git directory, no tests, no CI
# configuration, no local .env file. This is the second layer of defense next
# to .dockerignore (defense in depth).
COPY app ./app

USER appuser

# Documentation only: it states which port the application listens on. The port
# is opened to the outside by the -p flag of docker run.
EXPOSE 8000

# The container reports its own health. It uses the same GET / endpoint that
# was written as a health check at the start of the course.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

# --host 0.0.0.0 is needed so the application is reachable from outside the
# container. On 127.0.0.1 it would only be reachable from inside it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
