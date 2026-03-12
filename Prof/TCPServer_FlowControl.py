import socket


quotes = []
quotes.append("The Internet is literally a network of networks.")
quotes.append("The Internet lives where anyone can access it.")
quotes.append("The idea that you can somehow erase the Internet is silly.")

serverPort = 12000
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serverSocket.bind(('127.0.0.127', serverPort))
serverSocket.listen(8)
print('The server is ready to receive')

while True:
     connectionSocket, addr = serverSocket.accept()
     i = 0
     for quote in quotes:
          connectionSocket.send(quote.encode())
          print(i)
          i += 1
     connectionSocket.close()
