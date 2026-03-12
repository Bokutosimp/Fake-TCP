import socket

class Server:
    """
    TCP Server class for receiving messages from clients.
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.bind((self.__server_ip, self.__server_port))

    def receive(self):
        """
        Receive a message from a client.
        """
        print(f"Server listening on {self.__server_ip}:{self.__server_port}...")

        data, addr = self.__socket.recvfrom(1024)
        message = data.decode('utf-8')
        print(f"Received message from {addr}: {message}")
        return message

class Client:
    """
    TCP Client class for sending messages to a server.
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.connect((self.__server_ip, self.__server_port))

    def send_message(self, message: str):
        """
        Send a message to the server.
        """
        payload = message.encode('utf-8')
        self.__socket.send(payload)
        print(f"Sent message: {message}")
