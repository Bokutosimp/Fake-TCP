import logging
from sys import argv

from controller import Server

def main():
    try:
        server_ip = argv[1]
        server_port = int(argv[2])
    except Exception:
        print("Usage: python urft_server.py <server_ip> <server_port>")
        return

    try:
        server = Server(server_ip=server_ip, server_port=server_port)
        server.receive()
    except TimeoutError:
        logging.warning("timeout...")
    except ConnectionRefusedError:
        logging.warning("connection refused...")

if __name__ == "__main__":
    main()