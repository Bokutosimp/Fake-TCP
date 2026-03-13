# URFT (UDP Reliable File Transfer)

## Setup

### Prerequisites
- Python **3.8+**
- Linux VM / Linux environment
- No external dependencies (stdlib only)

### (Optional) Use a Python 3.8 virtualenv

```bash
python3.8 -m venv .venv38
source .venv38/bin/activate
python --version
```

## Run

### Start server

```bash
python3 urft_server.py <server_ip> <server_port>
```

Example:

```bash
python3 urft_server.py 0.0.0.0 5000
```

### Start client (another terminal)

```bash
python3 urft_client.py <file_path> <server_ip> <server_port>
```

Example:

```bash
python3 urft_client.py testfiles/alice.txt 127.0.0.1 5000
```

After a successful transfer, the server writes the received file to the **current directory** using the same basename as `<file_path>`.

### Verify integrity

```bash
md5sum testfiles/alice.txt alice.txt
```

## (Optional) Run with netem conditions

If you have `sudo` + `tc` working:

```bash
chmod +x test_network.sh
./test_network.sh testfiles/alice.txt
```
