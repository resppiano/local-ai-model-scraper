#!/usr/bin/env bash
# Start the Fable Agent MCP server
# Usage: ./start_fable_agent.sh

cd "$(dirname "$0")"
source venv/bin/activate

export FABLE_API_URL="http://localhost:8001"
export FABLE_ASSETS_DIR="/home/gregjones/FableAssets"
export HF_API_KEY="b9054caf-91a5-463f-b8eb-a566fe9e7eff"
export HF_SECRET="85a9b31f1ef4ba8baad049c7443aa22f6c2958715508ec000dc0738c574cf2aa"

exec python fable_agent.py
