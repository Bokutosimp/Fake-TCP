# Fake-TCP

A computer networking project implementing a custom file transfer protocol (URFT) and TCP flow control demonstrations.

## Project Overview

This project contains:
- **URFT (Custom Protocol) Implementation**: A client-server file transfer system
- **TCP Flow Control Demonstrations**: Reference implementations showing TCP buffer management
- **Network Simulation Tools**: For testing and validating network behavior

## Setup

### Prerequisites
- Python 3.8 or higher
- Linux/Unix environment (for shell scripts)

### Installation

1. **Clone/Navigate to the project directory**:
   ```bash
   cd Fake-TCP
   ```

2. **Create a Python virtual environment** (optional but recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **No external dependencies required** - this project uses only Python standard library

## Running the Lab

### URFT File Transfer Protocol

#### Start the Server
```bash
python urft_server.py <server_ip> <server_port>
```

Example:
```bash
python urft_server.py 127.0.0.1 5000
```

#### Start the Client (in another terminal)
```bash
python urft_client.py <filename> <server_ip> <server_port>
```

Example:
```bash
python urft_client.py testfiles/alice.txt 127.0.0.1 5000
```

### TCP Flow Control Demonstrations

Navigate to the `Prof/` directory to run reference implementations:

#### Start the Flow Control Server
```bash
python Prof/TCPServer_FlowControl.py
```

The server will listen on `127.0.0.127:12000` and send sample quotes.

#### Start the Flow Control Client (in another terminal)
```bash
python Prof/TCPClient_FlowControl.py
```

The client will:
1. Prompt you to set the socket receive buffer size
2. Allow you to interactively specify how many bytes to read in each request
3. Display received data from the server

### Automated Testing

Run the simulation script:
```bash
./simulate.sh
```

## Project Structure

```
Fake-TCP/
├── controller.py          # Main URFT protocol implementation
├── urft_server.py         # URFT server entry point
├── urft_client.py         # URFT client entry point
├── urft_client.py         # Network simulation utilities
├── simulate.sh            # Automated test script
├── Prof/                  # Reference implementations
│   ├── TCPServer_FlowControl.py
│   └── TCPClient_FlowControl.py
├── testfiles/             # Sample files for transfer
│   ├── alice.txt
│   └── lorem.txt
└── README.md
```

## Key Concepts Demonstrated

- **Custom Protocol Design**: URFT implementation for reliable file transfer
- **TCP Flow Control**: Buffer management and data transmission control
- **Client-Server Architecture**: Network communication patterns
- **Socket Programming**: Using Python's socket library for network communication
