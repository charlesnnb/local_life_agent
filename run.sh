#!/usr/bin/env bash

set -euo pipefail


usage() {
  echo "Usage: ./run.sh demo [scenario] [--check]" >&2
  echo "       ./run.sh hybrid [restaurant_full] [--check]" >&2
  echo "       ./run.sh live [--check]" >&2
}


read_env_value() {
  local file="$1"
  local key="$2"

  awk -v key="$key" '
    index($0, key "=") == 1 {
      value = substr($0, length(key) + 2)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^["\047]|["\047]$/, "", value)
      print value
      exit
    }
  ' "$file"
}


port_is_in_use() {
  local port="$1"
  python - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as client:
    client.settimeout(0.2)
    sys.exit(0 if client.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
}


mode="${1:-}"
if [[ "$mode" != "demo" && "$mode" != "hybrid" && "$mode" != "live" ]]; then
  usage
  exit 2
fi

scenario="normal"
scenario_set=false
check_only=""
for argument in "${@:2}"; do
  if [[ "$argument" == "--check" ]]; then
    if [[ -n "$check_only" ]]; then
      usage
      exit 2
    fi
    check_only="--check"
    continue
  fi
  if [[ "$scenario_set" == true ]]; then
    usage
    exit 2
  fi
  if [[ "$mode" == "live" ]]; then
    echo "Demo scenarios are not available in live mode." >&2
    exit 2
  fi
  if [[ "$mode" == "hybrid" ]]; then
    if [[ "$argument" != "normal" && "$argument" != "restaurant_full" ]]; then
      echo "Hybrid mode only supports restaurant_full as a deterministic scenario." >&2
      exit 2
    fi
    scenario="$argument"
    scenario_set=true
    continue
  fi
  case "$argument" in
    normal|restaurant_full|activity_unavailable|traffic_delay)
      scenario="$argument"
      scenario_set=true
      ;;
    *)
      echo "Unknown Demo scenario: $argument" >&2
      exit 2
      ;;
  esac
done

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="${LOCAL_LIFE_PROJECT_ROOT:-$script_root}"

# Clear profile variables so stale parent-environment values don't leak in.
profile_variables=(
  HOST
  PORT
  RUN_MODE
  DEMO_MODE
  DEMO_SCENARIO
  USE_MOCK_LLM
  USE_MOCK_AMAP
  USE_MOCK_ACTIONS
  ENABLE_LLM
  DEEPSEEK_API_KEY
  DEEPSEEK_BASE_URL
  DEEPSEEK_MODEL
  LLM_TIMEOUT_SECONDS
  ENABLE_AMAP
  AMAP_WEB_SERVICE_KEY
  AMAP_API_KEY
  AMAP_BASE_URL
  AMAP_TIMEOUT_SECONDS
  FRONTEND_PORT
)
unset "${profile_variables[@]}"

# Source the user's local .env for optional API keys (e.g. DEEPSEEK_API_KEY,
# AMAP_WEB_SERVICE_KEY). The file is gitignored and never committed.
dot_env="$project_root/.env"
if [[ -f "$dot_env" ]]; then
  set -a
  source "$dot_env"
  set +a
fi

# Mode-specific overrides — these are authoritative regardless of .env.
export RUN_MODE="$mode"
export DEMO_SCENARIO="$scenario"
case "$mode" in
  demo)
    export DEMO_MODE=true
    export USE_MOCK_LLM=true
    export USE_MOCK_AMAP=true
    export USE_MOCK_ACTIONS=true
    export ENABLE_LLM=false
    export ENABLE_AMAP=false
    ;;
  hybrid)
    export DEMO_MODE=false
    export USE_MOCK_LLM=false
    export USE_MOCK_AMAP=false
    export USE_MOCK_ACTIONS=true
    export ENABLE_LLM=true
    export ENABLE_AMAP=true
    ;;
  live)
    export DEMO_MODE=false
    export USE_MOCK_LLM=false
    export USE_MOCK_AMAP=false
    export USE_MOCK_ACTIONS=false
    export ENABLE_LLM=true
    export ENABLE_AMAP=true
    ;;
esac

if [[ "$mode" == "hybrid" || "$mode" == "live" ]]; then
  missing=()
  if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    missing+=("DEEPSEEK_API_KEY (set in .env)")
  fi
  if [[ -z "${AMAP_WEB_SERVICE_KEY:-${AMAP_API_KEY:-}}" ]]; then
    missing+=("AMAP_WEB_SERVICE_KEY or AMAP_API_KEY (set in .env)")
  fi

  frontend_env="$project_root/frontend/.env"
  if [[ -f "$frontend_env" ]]; then
    frontend_amap_key="$(read_env_value "$frontend_env" "VITE_AMAP_JS_KEY")"
  else
    frontend_amap_key=""
  fi
  if [[ -z "$frontend_amap_key" ]]; then
    missing+=("VITE_AMAP_JS_KEY (set in frontend/.env)")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    profile_label="Live"
    if [[ "$mode" == "hybrid" ]]; then
      profile_label="Hybrid"
    fi
    echo "$profile_label profile is incomplete. Set these values:" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    exit 1
  fi
fi

echo "Profile check passed: $mode"
if [[ "$mode" == "demo" || "$scenario" != "normal" ]]; then
  echo "Demo scenario: $DEMO_SCENARIO"
fi
if [[ "$check_only" == "--check" ]]; then
  exit 0
fi

backend_port="${PORT:-8000}"
frontend_port="${FRONTEND_PORT:-5173}"
if port_is_in_use "$backend_port"; then
  echo "Backend port $backend_port is already in use." >&2
  echo "Stop the existing process before switching profiles." >&2
  exit 1
fi
if port_is_in_use "$frontend_port"; then
  echo "Frontend port $frontend_port is already in use." >&2
  echo "Vite will not switch to another port; stop the existing process." >&2
  exit 1
fi

echo "Starting backend: http://localhost:$backend_port"
echo "Starting frontend: http://localhost:$frontend_port"
echo "Runtime profile: $mode"

(
  cd "$project_root"
  exec python run_backend.py
) &
backend_pid=$!

(
  cd "$project_root/frontend"
  exec "$project_root/frontend/node_modules/.bin/vite" \
    --mode "$mode" \
    --port "$frontend_port" \
    --strictPort
) &
frontend_pid=$!

cleanup() {
  kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" 2>/dev/null || true
  wait "$frontend_pid" 2>/dev/null || true
}

on_signal() {
  exit 130
}

trap cleanup EXIT
trap on_signal INT TERM

while kill -0 "$backend_pid" 2>/dev/null \
  && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done

set +e
if ! kill -0 "$backend_pid" 2>/dev/null; then
  wait "$backend_pid"
  status=$?
  kill "$frontend_pid" 2>/dev/null || true
else
  wait "$frontend_pid"
  status=$?
  kill "$backend_pid" 2>/dev/null || true
fi
set -e

exit "$status"
