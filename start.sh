#!/bin/bash
cd "$(dirname "$0")"
export CRUCELINE_DB="${CRUCELINE_DB:-/tmp/cruceline.db}"
export PORT="${PORT:-5055}"
python3 server.py
