#!/usr/bin/env bash
set -euo pipefail

# paths (fixed assignments - no spaces around =)
python_env=/home/rodolfo_danese/AI_compliance2/Info_extraction_fornitori/info_extraction_fornitori/bin/python
backend_dir=/home/rodolfo_danese/AI_compliance2/checkpoint1912NEEDTESTS/backend
main_api_backend_file=$backend_dir/main.py

# port: can be set via env PORT or positional arg, default 8000
PORT="5020"

LOGFILE="$backend_dir/backend.log"
mkdir -p "$(dirname "$LOGFILE")"

# initialize log with port and placeholder PID
printf "PORT: %s\nPID: starting...\n\n" "$PORT" > "$LOGFILE"

# detect python interpreter (accept either direct executable, virtualenv dir, or system python)
if [ -x "$python_env" ]; then
    PYTHON="$python_env"
elif [ -d "$python_env" ] && [ -x "$python_env/bin/python" ]; then
    PYTHON="$python_env/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
else
    echo "Error: python interpreter not found at $python_env and no python3/python in PATH" >&2
    exit 1
fi


# start the backend with nohup, append output to logfile
# export PORT so the child process inherits it
export PORT
nohup "$PYTHON" "$main_api_backend_file" >> "$LOGFILE" 2>&1 &

PID=$!

# write the real PID as the second line of the log
sed -i "2s/.*/PID: $PID/" "$LOGFILE"

echo "Started $main_api_backend_file (PID $PID) on port $PORT; log: $LOGFILE"