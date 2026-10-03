#!/bin/bash
set -e
cd /opt/trading/repo
export PYTHONPATH=/opt/trading/repo
.venv/bin/python -m trading_exec.morning --log exec_data/morning.log
