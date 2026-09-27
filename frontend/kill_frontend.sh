#!/usr/bin/env bash
lsof -t -i:3000 | xargs kill -9
echo "Frontend on port 3000 has been stopped."
