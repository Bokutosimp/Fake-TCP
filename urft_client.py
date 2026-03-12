import logging
from sys import argv

from controller import Client

def main():
    try:
        filename = argv[1]
        server_ip = argv[2]
        server_port = int(argv[3])
    except Exception:
        print("Usage: python urft_client.py <filename> <server_ip> <server_port>")
        return

    try:
        client = Client(server_ip=server_ip, server_port=server_port)
        client.send_message(filename)
    except TimeoutError:
        logging.warning("timeout...")
    except ConnectionRefusedError:
        logging.warning("connection refused...")

if __name__ == "__main__":
    main()