import socket
import threading

hostname = socket.gethostname()

HEADER = 64
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"
PORT = 5050
SERVER = socket.gethostbyname(hostname)  # get host IP address of the current device
ADDR = (SERVER, PORT)  # couple IP address and port number

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)  # bind the port and IP


def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT)  # get length of the incoming message (separate message)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)  # read the message
            print(f"[{addr}] {msg}")
            conn.send("Message received.".encode(FORMAT))
            if msg == DISCONNECT_MESSAGE:
                connected = False
    conn.close()


def start():
    server.listen()  # start listening for incoming messages
    print(f"[LISTENING] Server is listening on {SERVER}")
    while True:
        conn, addr = server.accept()  # wait to accept any incoming messages
        thread = threading.Thread(target=handle_client, args=(conn, addr))  # handle messages in a separate thread
        thread.start()
        # show number of active threads/connections (excluding the one running start())
        print(f"\n[ACTIVE CONNECTIONS] {threading.active_count() - 1}")


if __name__ == "__main__":
    print("[STARTING] Server is starting...")
    start()
