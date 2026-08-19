#!/usr/bin/env bash
#
# Run a command with a per-attempt timeout and bounded retries.
#
# A step-level `timeout-minutes:` bounds the whole step, which is enough to
# stop a stall burning the six-hour job ceiling but not enough to recover from
# one: the first attempt hangs, eats the entire budget, and the step dies with
# no retry ever reached. The timeout has to sit on each *attempt* for a retry
# to be worth having. That is what this exists for — `timeout-minutes:` stays
# on the step as the outer backstop.
#
# Usage:
#   retry.sh [--attempts N] [--timeout SECONDS] [--delay SECONDS] -- cmd [args...]
#
# Defaults: 3 attempts, 300s per attempt, 15s base delay (linear backoff).
# Exit status is the last attempt's, or 124 if the last attempt timed out.

set -uo pipefail

attempts=3
per_attempt_timeout=300
delay=15

while [ $# -gt 0 ]; do
  case "$1" in
    --attempts) attempts="$2"; shift 2 ;;
    --timeout) per_attempt_timeout="$2"; shift 2 ;;
    --delay) delay="$2"; shift 2 ;;
    --) shift; break ;;
    *) echo "retry.sh: unknown option '$1'" >&2; exit 2 ;;
  esac
done

if [ $# -eq 0 ]; then
  echo "retry.sh: no command given" >&2
  exit 2
fi

# `timeout` is coreutils and is absent on the macOS runners, where Homebrew
# coreutils installs it as `gtimeout`. Fall back to a shell watchdog so this
# behaves the same on every runner we use rather than silently running
# unbounded on one of them.
run_with_timeout() {
  local limit="$1"; shift
  # `-k 5` escalates to SIGKILL five seconds after SIGTERM, matching what the
  # watchdog below does, so a command that ignores TERM cannot outlive its
  # bound on either path.
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 5 "$limit" "$@"
    return $?
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout -k 5 "$limit" "$@"
    return $?
  fi

  # The watchdog marks the file immediately before signalling. Liveness is not
  # usable as the signal here: after `kill -TERM` the watchdog is still in its
  # grace sleep, so it looks alive while the command it just killed reports
  # 143. The marker distinguishes "timed out" from "died on its own" exactly.
  local marker
  marker="$(mktemp)"
  rm -f "$marker"

  "$@" &
  local cmd_pid=$!
  (
    sleep "$limit"
    : > "$marker"
    kill -TERM "$cmd_pid" 2>/dev/null && sleep 5 && kill -KILL "$cmd_pid" 2>/dev/null
  ) >/dev/null 2>&1 &
  local watchdog_pid=$!

  local status=0
  wait "$cmd_pid" 2>/dev/null || status=$?
  kill -TERM "$watchdog_pid" 2>/dev/null
  wait "$watchdog_pid" 2>/dev/null || true
  # Report 124 the way coreutils `timeout` does, so both paths agree.
  if [ -f "$marker" ]; then
    status=124
  fi
  rm -f "$marker"
  return "$status"
}

status=0
attempt=1
while [ "$attempt" -le "$attempts" ]; do
  status=0
  run_with_timeout "$per_attempt_timeout" "$@" || status=$?

  if [ "$status" -eq 0 ]; then
    if [ "$attempt" -gt 1 ]; then
      echo "retry.sh: succeeded on attempt ${attempt}/${attempts}"
    fi
    exit 0
  fi

  if [ "$status" -eq 124 ]; then
    reason="timed out after ${per_attempt_timeout}s"
  else
    reason="exited ${status}"
  fi

  if [ "$attempt" -eq "$attempts" ]; then
    echo "::error::retry.sh: attempt ${attempt}/${attempts} ${reason}; no attempts left"
    break
  fi

  backoff=$((delay * attempt))
  echo "::warning::retry.sh: attempt ${attempt}/${attempts} ${reason}; retrying in ${backoff}s"
  sleep "$backoff"
  attempt=$((attempt + 1))
done

exit "$status"
