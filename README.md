# CI/CD and DevSecOps demo

A minimal FastAPI application with a GitHub Actions pipeline around it.

This repository is the teaching demo for the DEDIH 2.0 / ELTE "CI/CD and DevSecOps" course. It
exists so the road from a plain CI baseline to the security gates (branch protection, secret
scanning, image scanning, an automated review) can be shown on a small but real project rather than
on slides.

Participant facing material is Hungarian. This README, the code comments and the workflow comments
are English.

## Stack

- Python 3.11+
- FastAPI + Pydantic
- pytest, ruff
- GitHub Actions
- Docker
- gitleaks (secret scanning), Trivy (image scanning), Ollama (the model for the review job)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running it

Tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

Format:

```bash
ruff format .
```

Local server:

```bash
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>

## The endpoints

| Endpoint | What it does |
| --- | --- |
| `GET /` | Health check. Returns `{"status": "ok"}`. |
| `POST /greet` | Returns a greeting. The name is validated by Pydantic, 1 to 50 characters. |
| `GET /config` | Reports whether an API key is configured, without returning the value. |

`GET /config` is what makes the secret load bearing. `app/config.py` reads the `OPENAI_API_KEY`
environment variable, the endpoint answers `{"api_key_configured": false}` while nothing is set, and
`true` once the workflow injects the secret. The value itself is never returned and never logged.

## Branches

| Branch | What is on it |
| --- | --- |
| `main` | The green baseline. Three endpoints, five tests. |
| `feature/bad-pr` | A boundary test that contradicts the validation in `app/models.py`. CI is red. |
| `secrets-leak` | A hardcoded credential in `app/config.py`, marked `DONOTUSE`. The secret scan is red. |

Both demo branches exist to be opened as a pull request against `main` inside a fork, so the
participants see a red required check block a merge in their own repository.

## The workflows

| File | Trigger | What it does |
| --- | --- | --- |
| `.github/workflows/ci.yml` | every push and pull request | `build-and-test`: lint, format check, tests. `secret-scan`: gitleaks over the working tree. |
| `.github/workflows/docker.yml` | manual | Builds the image, smoke tests it, then scans it twice with Trivy. |
| `.github/workflows/deploy.yml` | manual | Shows how a secret reaches a job, what a scope means, and what an environment gate adds. |
| `.github/workflows/ai-review.yml` | manual | Downloads a small model onto the runner and posts its review as a pull request comment. |

Two more files sit next to them:

| File | What it is |
| --- | --- |
| `.github/actions/setup/action.yml` | A composite action: set up Python, install the dependencies. Used by every job that needs Python. |
| `.github/workflows/reusable-checks.yml` | A reusable workflow that runs the lint and the tests as its own job. `deploy.yml` calls it. |

The two are the same idea with different mechanics, and the difference is not cosmetic. A composite
action runs inside the calling job, so it works under a job that has `environment:` set and it sees
the `env:` of that job. A reusable workflow runs as its own job and the calling job cannot set an
`environment:` on it, because `on.workflow_call` does not support that keyword. Environment scoped
secrets therefore never reach a reusable workflow, with or without `secrets: inherit`. `deploy.yml`
uses both, so the difference is visible in a single run.

## Image scanning

`docker.yml` runs Trivy twice against the same built image, with different filters. Trivy reads both
the Debian packages of the base layer and the Python packages in the virtualenv at `/opt/venv`,
which is why there is no separate tool reading `requirements.txt`: it would be the same check twice,
on a smaller surface.

| | Gate | Report |
| --- | --- | --- |
| Scope | `--pkg-types library`, our own packages | `--pkg-types os,library`, everything |
| Findings with no fix | excluded, `--ignore-unfixed` | included |
| Severity | `--severity HIGH,CRITICAL` | every severity |
| On a finding | `--exit-code 1`, the job goes red | `--exit-code 0`, never fails |
| Output | the step log and the job summary | the job summary and an artifact |

The principle behind the split: what blocks you has to be actionable, what informs you can be
complete. A gate that fires on things nobody can fix gets switched off within a month, and then you
have neither the gate nor the information.

The gap between the two numbers is the lesson of the exercise. The gate counts what we chose. The
report counts what we actually ship, and most of that comes from the base image.

## Updating a dependency

There is no automatic fix command. Trivy names the package, the installed version and the version
that carries the fix. The remediation is to raise the pin in `requirements.txt` by hand, then check
that nothing broke:

```bash
pytest
ruff check .
ruff format --check .
docker build -f docker/Dockerfile -t dedih-demo:local .
```

When the finding is in a transitive dependency, the pin to raise is the one that pulls it in.
`starlette` is not in `requirements.txt`, `fastapi` is, and raising `fastapi` is what moves
`starlette`.

**The pins in `requirements.txt` are deliberately old.** They are what gives the supply chain
exercise real findings instead of planted ones. Nothing here is fabricated: the CVEs are genuine,
they are simply not fixed on purpose. Before a delivery it is worth rerunning the scan, because the
vulnerability database moves and the counts move with it.

## Docker image

| File | Role |
| --- | --- |
| `docker/Dockerfile` | Multi-stage build with a non-root user. |
| `.dockerignore` | Says what must stay out of the build context. |

### Local build

```bash
docker build -f docker/Dockerfile -t dedih-demo:local .
docker run --rm -p 8000:8000 dedih-demo:local
```

`-f` gives the location of the Dockerfile, the trailing `.` gives the build context, which is the
directory Docker receives. The two are not the same thing.

The Swagger UI is then at <http://127.0.0.1:8000/docs>, the same as with a local `uvicorn` run.

### What the image demonstrates

- **multi-stage build**: the packages are installed in a separate stage, and only the finished
  virtualenv and the application code go into the shipped image
- **pinned base image**: `python:3.11-slim-bookworm` is pinned, not `latest`, because the base image
  is a dependency we did not write
- **non-root user**: the application runs as `appuser`, not as root
- **no package installer in the runtime image**: the system `site-packages` of the base image is
  removed, which takes away both a set of findings nobody would otherwise fix and a working
  installer for anyone who gets a shell in the container
- **`.dockerignore`**: the `.git` directory does not go into the image. A secret deleted from a file
  can still be in the commit history, and a `COPY . .` would package that history into the image

### Scanning the image locally

```bash
docker build -f docker/Dockerfile -t dedih-demo:local .

# Gate: our own packages, fixable findings only, HIGH and CRITICAL only
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.74.0 \
  image --scanners vuln --pkg-types library --ignore-unfixed \
  --severity HIGH,CRITICAL --exit-code 1 dedih-demo:local

# Report: everything, including the base operating system and the unfixable
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.74.0 \
  image --scanners vuln --pkg-types os,library --exit-code 0 dedih-demo:local
```

## Scanning for secrets locally

```bash
# The working tree, which is what the CI gate looks at
docker run --rm -v "$PWD":/scan zricethezav/gitleaks:v8.30.1 \
  dir /scan --no-banner --redact

# The commit history, which is where a deleted value still lives
docker run --rm -v "$PWD":/scan zricethezav/gitleaks:v8.30.1 \
  git /scan --no-banner --redact
```

The two commands answering differently is the point of the secrets block. The CI gate going green
after the value is deleted does not mean the key is gone. It means the current files are clean. The
key is still in the history, and the only real remediation is to rotate it.
