import socket
import errno
import sys
import threading
from time import sleep


HEADER_LENGTH = 10

IP = "127.0.0.1"
PORT = 1234
my_username = input("Username: ")

# Create a socket.
# socket.AF_INET - address family, IPv4, some other possible are AF_INET6, AF_BLUETOOTH, AF_UNIX
# socket.SOCK_STREAM - TCP, connection-based, socket.SOCK_DGRAM - UDP, connectionless, datagrams, socket.SOCK_RAW - raw
# IP packets
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to a given ip and port
client_socket.connect((IP, PORT))

# Set connection to non-blocking state, so .recv() call won't block, just return some exception we'll handle
client_socket.setblocking(False)

# Prepare username and header and send them
# We need to encode username to bytes, then count number of bytes and prepare header of fixed size, that we encode to
# bytes as well
username = my_username.encode("utf-8")
username_header = f"{len(username):<{HEADER_LENGTH}}".encode("utf-8")
client_socket.send(username_header + username)


# Function that will handle incoming messages parallel to anything else we do - it is meant to be executed from a
# separate thread
def handle_incoming_messages():
    while True:
        sleep(0.1)
        try:
            # Now we want to loop over received messages (there might be more than one) and print them
            while True:
                # Receive our "header" containing username length, it's size is defined and constant
                _username_header = client_socket.recv(HEADER_LENGTH)

                # If we received no data, server gracefully closed a connection, for example using socket.close() or
                # socket.shutdown(socket.SHUT_RDWR)
                if not len(_username_header):
                    print("connection closed by the server.")
                    sys.exit()

                # Convert header to int value
                username_length = int(_username_header.decode("utf-8").strip())

                # Receive and decode username
                _username = client_socket.recv(username_length).decode("utf-8")

                # Now do the same for message (as we received username, we received whole message, there's no need to
                # check if it has any length)
                _message_header = client_socket.recv(HEADER_LENGTH)
                message_length = int(_message_header.decode("utf-8").strip())
                _message = client_socket.recv(message_length).decode("utf-8")

                # Print message
                print(f"\r{_username} > {_message}")

        except IOError as e:
            # This is normal on non-blocking connections - when there are no incoming data error is going to be raised
            # Some operating systems will indicate that using EAGAIN, and some using EWOULDBLOCK error code
            # We are going to check for both - if one of them - that's expected, means no incoming data, continue as
            # normal. If we got different error code - something happened
            if e.errno not in [errno.EAGAIN, errno.EWOULDBLOCK]:
                print(f"Reading error: {e}")
                sys.exit()

            # We just did not receive anything
            continue

        except Exception as e:
            # Any other exception - something happened, exit
            print(f"An error has occurred: {e}")
            sys.exit()


while True:
    handle_incoming_messages_thread = threading.Thread(target=handle_incoming_messages)
    handle_incoming_messages_thread.start()

    # Wait for user to input a message
    message = input()

    # If message is not empty - send it
    if message:

        # Encode message to bytes, prepare header and convert to bytes, like for username above, then send
        # print(f"{my_username} > {message}")
        message = message.encode("utf-8")
        message_header = f"{len(message):<{HEADER_LENGTH}}".encode("utf-8")
        client_socket.send(message_header + message)

