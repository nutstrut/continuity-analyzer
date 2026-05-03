#!/bin/bash
cd /home/ubuntu/continuity-analyzer
source venv/bin/activate
uvicorn continuity_analyzer:app --host 127.0.0.1 --port 3002
