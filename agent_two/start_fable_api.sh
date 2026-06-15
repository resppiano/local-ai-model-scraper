#!/usr/bin/env bash
# Start the Fable API backend
# Usage: ./start_fable_api.sh

cd "$(dirname "$0")"
source venv/bin/activate

export FABLE_DB_PATH="/home/gregjones/agent_two/fable_api/fable.db"
export FABLE_ASSETS_DIR="/home/gregjones/FableAssets"
export HF_API_KEY="b9054caf-91a5-463f-b8eb-a566fe9e7eff"
export HF_SECRET="85a9b31f1ef4ba8baad049c7443aa22f6c2958715508ec000dc0738c574cf2aa"

exec python -m uvicorn fable_api.main:app --host 0.0.0.0 --port 8001 --workers 1
