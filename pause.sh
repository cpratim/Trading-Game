#!/usr/bin/env bash
PORT=${1:-5002}
curl -s -X POST "http://localhost:$PORT/admin/pause" && echo "Book $PORT paused."
