#!/usr/bin/env bash
cd "$HOME/roxy_trading" || exit 1
source .venv/bin/activate
mkdir -p logs
python app.py >> logs/roxy_run.log 2>&1
