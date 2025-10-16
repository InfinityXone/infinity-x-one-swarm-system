#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_MODE:-service}" == "job" ]]; then
  exec python -u job_main.py
else
  exec uvicorn main:app --host=0.0.0.0 --port="${PORT:-8080}"
fi
