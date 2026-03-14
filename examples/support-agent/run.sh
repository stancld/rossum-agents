#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

claude --model claude-haiku-4-5-20251001 --dangerously-skip-permissions
