#!/bin/bash

function setup_network() {
  echo "[NETWORK] Setting up simulation (Delay: $1ms, Loss: $2%, Duplicate: $3%)"
  sudo tc qdisc add dev lo root netem delay "$1"ms loss "$2"% duplicate "$3"%
}

function reset_network() {
  echo "[NETWORK] Resetting network simulation"
  sudo tc qdisc del dev lo root 2>/dev/null
}

reset_network
setup_network 200 50 0

echo "--- Starting Server ---"
# Using standard python3 (will use your venv if activated)
python3 urft_server.py 127.0.0.1 8080 &
SERVER_PID=$!

sleep 1

echo "--- Running Client ---"
# Using standard python3 (will use your venv if activated)
python3 urft_client.py "Testing_My_UDP_Code!" 127.0.0.1 8080

sleep 2

echo "--- Cleaning up ---"
kill $SERVER_PID
reset_network
echo "Test complete."