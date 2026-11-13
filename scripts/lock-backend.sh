#!/usr/bin/env bash
# Regenerates the pinned backend dependency locks from backend/pyproject.toml (the ranges stay the source of truth).
#   requirements-server.lock  Linux, extra `server`                (deploy/api.Dockerfile installs this)
#   requirements-ci.lock      Linux, extras server+worker+dev      (CI installs this)
#   requirements-worker.lock  this machine (the Mac), extra `worker`  (deploy/worker/install-worker.sh installs this)
# Commit the result. Run when bumping a dependency range or to pick up newer versions; needs Docker and python3.12.
set -euo pipefail
cd "$(dirname "$0")/../backend"
OPTS="--quiet --no-header --strip-extras --no-emit-index-url --resolver=backtracking"
docker run --rm -v "$PWD":/b -w /b python:3.12-slim sh -c "
  pip install -q pip-tools &&
  pip-compile $OPTS --extra server -o requirements-server.lock pyproject.toml &&
  pip-compile $OPTS --extra server --extra worker --extra dev -o requirements-ci.lock pyproject.toml"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
python3.12 -m venv "$T/v" && "$T/v/bin/pip" install -q pip-tools
"$T/v/bin/pip-compile" $OPTS --extra worker -o requirements-worker.lock pyproject.toml
echo "locks regenerated: review the diff, run the backend tests, commit"
