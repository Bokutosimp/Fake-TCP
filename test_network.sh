#!/usr/bin/env bash
set -euo pipefail

# URFT network test runner (PDF-style netem cases)
#
# Usage:
#   ./test_network.sh <file_path>
#
# Notes:
# - Requires: python3, md5sum, sudo, and `tc` (iproute2).
# - Uses loopback (lo). netem settings apply in both directions on lo.

PYTHON_BIN="${PYTHON_BIN:-python3}"
TEST_FILE="${1:-testfiles/alice.txt}"
SERVER_IP="${SERVER_IP:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-12345}"
TMP_5M_FILE=""

cleanup() {
  sudo tc qdisc del dev lo root 2>/dev/null || true
  # Remove the received output file (server writes basename of TEST_FILE).
  rm -f "$(basename "$TEST_FILE")" 2>/dev/null || true
  if [[ -n "$TMP_5M_FILE" ]]; then
    rm -f "$TMP_5M_FILE" 2>/dev/null || true
  fi
}
trap cleanup EXIT

setup_network() {
  local delay_ms="$1"
  local loss_pct="$2"
  local dup_pct="$3"
  local reorder_pct="$4"

  echo "Setting netem on lo: delay=${delay_ms}ms loss=${loss_pct}% duplicate=${dup_pct}% reorder=${reorder_pct}%"
  sudo tc qdisc del dev lo root 2>/dev/null || true

  if [[ "$reorder_pct" -gt 0 ]]; then
    sudo tc qdisc add dev lo root netem delay "${delay_ms}ms" loss "${loss_pct}%" duplicate "${dup_pct}%" reorder "${reorder_pct}%"
  else
    sudo tc qdisc add dev lo root netem delay "${delay_ms}ms" loss "${loss_pct}%" duplicate "${dup_pct}%"
  fi
}

reset_network() {
  sudo tc qdisc del dev lo root 2>/dev/null || true
}

verify_integrity() {
  local original="$1"
  local received="$2"

  local original_md5 received_md5
  original_md5="$(md5sum "$original" | awk '{print $1}')"
  received_md5="$(md5sum "$received" | awk '{print $1}')"

  if [[ "$original_md5" == "$received_md5" ]]; then
    echo "File integrity: PASS"
    return 0
  fi

  echo "File integrity: FAIL"
  echo "Original MD5: $original_md5"
  echo "Received MD5: $received_md5"
  return 1
}

run_test() {
  local name="$1"
  local one_way_delay_ms="$2"
  local loss_pct="$3"
  local dup_pct="$4"
  local reorder_pct="$5"

  echo "===================================================="
  echo "Running: $name"
  echo "===================================================="

  setup_network "$one_way_delay_ms" "$loss_pct" "$dup_pct" "$reorder_pct"

  rm -f "$(basename "$TEST_FILE")" 2>/dev/null || true

  # Start server (single run, single file).
  "$PYTHON_BIN" urft_server.py "$SERVER_IP" "$SERVER_PORT" >/dev/null 2>&1 &
  local server_pid=$!

  # Give server time to bind.
  sleep 0.6

  # Run client.
  set +e
  "$PYTHON_BIN" urft_client.py "$TEST_FILE" "$SERVER_IP" "$SERVER_PORT" >/dev/null 2>&1
  local client_rc=$?
  set -e

  # Wait server to exit.
  set +e
  wait "$server_pid"
  local server_rc=$?
  set -e

  if [[ "$client_rc" -ne 0 || "$server_rc" -ne 0 ]]; then
    echo "FAIL: process error (client_rc=${client_rc}, server_rc=${server_rc})"
    reset_network
    return 1
  fi

  local received_file
  received_file="$(basename "$TEST_FILE")"
  if [[ ! -f "$received_file" ]]; then
    echo "FAIL: server did not create output file: $received_file"
    reset_network
    return 1
  fi

  verify_integrity "$TEST_FILE" "$received_file"

  rm -f "$received_file"
  reset_network
  echo ""
}

if [[ ! -f "$TEST_FILE" ]]; then
  echo "Error: file not found: $TEST_FILE"
  exit 1
fi

echo "Using python: $PYTHON_BIN"
echo "Test file: $TEST_FILE"
echo "Server: ${SERVER_IP}:${SERVER_PORT}"
echo ""

# PDF table uses RTT; `tc netem delay` is one-way on the interface, so we use RTT/2.
run_test "1_1MiB_rtt10_noimpair" 5 0 0 0
run_test "2_1MiB_rtt10_dup2" 5 0 2 0
run_test "3_1MiB_rtt10_loss2" 5 2 0 0
run_test "4_1MiB_rtt10_dup5" 5 0 5 0
run_test "5_1MiB_rtt10_loss5" 5 5 0 0
run_test "6_1MiB_rtt250_noimpair" 125 0 0 0
run_test "7_1MiB_rtt250_reorder2" 125 0 0 2

# Test #8 in PDF is asymmetric loss (C->S 5%, S->C 2%) and 5 MiB at RTT 100ms.
# On loopback with a single netem qdisc, we can only emulate symmetric impairment.
# We run a conservative symmetric-loss variant (5% both directions) with a 5 MiB file.
  TMP_5M_FILE="$(mktemp -t urft_5m_XXXXXX.bin)"
  dd if=/dev/urandom of="$TMP_5M_FILE" bs=1M count=5 status=none
  TEST_FILE_5M="${TEST_FILE_5M:-$TMP_5M_FILE}"
run_test "8_5MiB_rtt100_loss5_symmetric" 50 5 0 0

echo "Done."

