#!/bin/bash
set -e
cd /opt/trading/repo
export PYTHONPATH=/opt/trading/repo
.venv/bin/python -m trading_exec.evening --log exec_data/evening.log
