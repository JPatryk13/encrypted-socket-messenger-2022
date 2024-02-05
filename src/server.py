import codecs
import os
import pickle
import socket
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from typing import Literal, Mapping, Type, Callable
from enum import Enum
from secrets import token_hex
from nacl.public import PrivateKey, SealedBox
from src.shared_enum_vars import ClientResponseTypes, ServerResponseTypes, ServerEventTypes
from src.message_handler import MessageHandler
from src.schema import MessageSchema, ServerClientCommunicationSchema, AddrType
import select
from src.slice_string import slice_string
from pydantic import BaseModel
from threading import Thread
from time import sleep, time


project_path = Path(__file__).parent.parent.resolve()
load_dotenv(dotenv_path=project_path / ".env")

FORMAT = os.getenv('FORMAT')
RESPONSE_TYPE_HEADER_LENGTH = int(os.getenv('RESPONSE_TYPE_HEADER_LENGTH'))
TIMESTAMP_HEADER_LENGTH = int(os.getenv('TIMESTAMP_HEADER_LENGTH'))
MESSAGE_ID_HEADER_LENGTH = int(os.getenv('MESSAGE_ID_HEADER_LENGTH'))
MESSAGE_LENGTH_HEADER_LENGTH = int(os.getenv('MESSAGE_LENGTH_HEADER_LENGTH'))
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS'))


class Server:
    def __init__(
            self,
            __debug: bool = False,
            __log_file_created_at: datetime = datetime.now(),
            __use_addr: tuple[str, int] = (socket.gethostbyname(socket.gethostname()), 0)
    ):
        # Generate passcode for client verification
        self.passcode: str = token_hex(64)

        # Instantiate message handlers. First one for messages between the server and clients, second one between
        # clients.
        self.server_messages: MessageHandler = MessageHandler(ServerClientCommunicationSchema, sort_messages_by_date=True)
        self.client_messages: MessageHandler = MessageHandler(MessageSchema, sort_messages_by_date=True)

        # Disallow reading/writing server_/client_messages when performing any other read or write - which may involve
        # sorting which, then, may result in reading unsorted messages. The handle_incoming_messages() before appending
        # any message (and automatically performed sorted() by the MessageHandler) will set the ..._messages_io_allowed
        # flag to False, append a message and set it back to True. The message_dispatcher() will set these flags to
        # False before reading messages.
        self.server_messages_io_allowed: bool = True
        self.client_messages_io_allowed: bool = True

        # initialize debug-related variables
        self.debug = __debug
        self.methods_called_debug: list[str] = []

        # filename for logging messages
        self.log_filename = "log_" + __log_file_created_at.strftime("%Y%m%d%H%M%S%f") + ".txt"

        # Create a socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Sets REUSEADDR to True (1)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to local IP address and instead of choosing port number, assign only the available one
        self.addr = __use_addr
        self.server_socket.bind(__use_addr)

        # list of all approved connections
        self.sockets_list = [self.server_socket]
        # [{"client_name": "...", "addr": (..., ...)}] - approved clients that sent their username
        self.clients_list: list[Mapping[str, str | AddrType]] = []

        # This makes server listen to new connections
        self.server_socket.listen()

        print(f"[SERVER] Listening at {self.addr}")

    def get_passcode(self) -> str:
        """
        Return generated passcode to the console - user then can copy it and give it to whomever he wants to message
        with.
        :return:
        """
        if self.debug:
            self.methods_called_debug.append("get_passcode")

        return self.passcode

    def get_addr(self) -> AddrType:
        if self.debug:
            self.methods_called_debug.append("get_addr")

        return self.server_socket.getsockname()

    def __get_client_id(self, client_socket: socket.socket) -> str:

        if self.debug:
            self.methods_called_debug.append("__get_client_id")

        # id=<ip_as_str><port_padded_with_zeros>
        ip_str = "".join(list(map(lambda x: x.zfill(3), client_socket.getpeername()[0].split('.'))))
        return ip_str + str(client_socket.getpeername()[1]).zfill(6)

    def handle_clients(
            self,
            *, client_socket,
            client_response_code: Literal[
                ClientResponseTypes.USERNAME_GIVEN,
                ClientResponseTypes.PASSCODE_GIVEN,
                ClientResponseTypes.CLIENT_DISCONNECTED
            ],
            client_message: str | None
    ) -> None:
        """
        Handle users that are joining the chat room. Validate passcodes and if correct, add clients to the list of
        connected clients or remove if their dropped out. Record appropriate messages in the message pool - these are to
        be sent out to other connected clients. Alter 'message.broadcasted' or 'message.broadcasted.user_connected'
        value accordingly.
        :return:
        """
        if self.debug:
            self.methods_called_debug.append("handle_clients")

        if client_response_code == ClientResponseTypes.PASSCODE_GIVEN:

            print(f"[SERVER - HC] Client sent passcode: {client_message}")

            # Validate passcode and if correct then add to sockets_list
            if client_message == self.passcode:

                print("[SERVER - HC] Passcode correct.")

                # Passcode correct add to sockets_list
                self.sockets_list.append(client_socket)

                print(f"[SERVER - HC] sockets_list: {self.sockets_list}")

                # Add PASSCODE_CORRECT response to server messages
                self.server_messages.append_message(
                    response_type=ServerResponseTypes.PASSCODE_CORRECT,
                    broadcasted=[{"client_name": pickle.dumps(client_socket.getpeername())}],
                    server_addr=self.server_socket.getsockname()
                )

                print(f"[SERVER - HC] server_messages: {self.server_messages}")

            else:

                print("[SERVER - HC] Passcode incorrect.")

                # Passcode incorrect add PASSCODE_INCORRECT to server messages
                self.server_messages.append_message(
                    response_type=ServerResponseTypes.PASSCODE_INCORRECT,
                    broadcasted=[{"client_name": pickle.dumps(client_socket.getpeername())}],
                    server_addr=self.server_socket.getsockname()
                )

                print(f"[SERVER - HC] server_messages: {self.server_messages}")

        elif client_response_code == ClientResponseTypes.USERNAME_GIVEN:

            print(f"[SERVER - HC] Client sent username: {client_message}")

            # Check if the username already exists
            for c in self.clients_list:

                if client_message == c["client_name"]:

                    # Respond to the client
                    self.server_messages.append_message(
                        response_type=ServerResponseTypes.USERNAME_ALREADY_EXISTS,
                        broadcasted=[{"client_name": pickle.dumps(client_socket.getpeername())}],
                        server_addr=self.server_socket.getsockname()
                    )

                    break

            else:

                # Add client to clients_list
                self.clients_list.append({"client_name": client_message, "addr": client_socket.getpeername()})

                print(f"[SERVER - HC] clients_list: {self.clients_list}")

                # Respond to the client
                self.server_messages.append_message(
                    response_type=ServerResponseTypes.USERNAME_ACCEPTED,
                    broadcasted=[{"client_name": client_message}],
                    server_addr=self.server_socket.getsockname()
                )

                if len(self.clients_list) > 1:

                    self.server_messages.append_message(
                        response_type=ServerResponseTypes.CLIENT_CONNECTED,
                        broadcasted=[{"client_name": c["client_name"]} for c in self.clients_list[:-1]],
                        server_addr=self.server_socket.getsockname(),
                        info=self.__get_client_id(client_socket) + client_message
                    )

                print(f"[SERVER - HC] server_messages: {self.server_messages}")

        else:
            # Client disconnected. Remove client from the sockets and clients lists.

            print("[SERVER - HC] Client disconnected")

            if client_socket in self.sockets_list:

                self.sockets_list.remove(client_socket)

            if client_socket.getpeername() in [c["addr"] for c in self.clients_list]:

                self.clients_list.remove(
                    next(
                        (
                            user for user in self.clients_list
                            if user["addr"] == client_socket.getpeername()
                        ),
                        None
                    )
                )

                # Inform other clients that client's disconnected
                self.server_messages.append_message(
                    response_type=ServerResponseTypes.CLIENT_DISCONNECTED,
                    broadcasted=[{"client_name": c["client_name"]} for c in self.clients_list],
                    server_addr=self.server_socket.getsockname(),
                    info=self.__get_client_id(client_socket)
                )

    def handle_missing_message(self) -> None:
        """
        Check if the message before the one just received was also received. No? Presume missing.
        :return:
        """
        if self.debug:
            self.methods_called_debug.append("handle_missing_message")

    def receive_message(
            self,
            client_socket: socket.socket
    ) -> tuple[ClientResponseTypes, datetime | None, datetime | None, int | None, str | None]:

        if self.debug:
            self.methods_called_debug.append("receive_message")

        response_type: ClientResponseTypes = ClientResponseTypes.CLIENT_DISCONNECTED
        client_sent_at: datetime | None = None
        server_received_at: datetime | None = None
        message_length: int | None = None
        message: str | None = None

        # noinspection PyBroadException
        try:
            self.log(
                ServerEventTypes.DEBUG,
                datetime.now(),
                func_name=self.receive_message.__name__,
                message="Waiting for message from the client..."
            )

            # Receive our "header" containing response type  and message length, it's size is defined and constant
            header = client_socket.recv(MESSAGE_LENGTH_HEADER_LENGTH + TIMESTAMP_HEADER_LENGTH + RESPONSE_TYPE_HEADER_LENGTH)

            self.log(
                ServerEventTypes.DEBUG,
                datetime.now(),
                func_name=self.receive_message.__name__,
                message="Retrieved message header",
                header=header
            )

            # record time when the message was received by the server
            server_received_at = datetime.now()

            if not len(header):
                # If we received no data, client gracefully closed a connection, for example using socket.close() or
                # socket.shutdown(socket.SHUT_RDWR)

                return ClientResponseTypes.CLIENT_DISCONNECTED, None, None, None, None

            else:

                print(f"[SERVER - RM] Message received at {server_received_at}.")

                # Extract response code, timestamp and message length from the header
                response_type, client_sent_at_str, message_length_str = slice_string(
                    header.decode(FORMAT),
                    [RESPONSE_TYPE_HEADER_LENGTH, TIMESTAMP_HEADER_LENGTH, MESSAGE_LENGTH_HEADER_LENGTH],
                    force_str=True
                )

                # read message length from message_length_str @ message header
                message_length = int(message_length_str)

                # read message and decode
                message = client_socket.recv(message_length).decode(FORMAT)

                # convert string like "20221226200114323957" to datetime(2022, 12, 26, 20, 1, 14, 323957)
                client_sent_at = datetime(*slice_string(client_sent_at_str, [4, 2, 2, 2, 2, 2, 6]))

                print(f"[SERVER - RM] Retrieving data... response_type: {response_type}, client_sent_at: {client_sent_at}, message_length: {message_length}, message: {message}")

                # Return an object of message header and message data
                return response_type, client_sent_at, server_received_at, message_length, message

        except Exception:
            # If we are here, client closed connection violently, for example by pressing ctrl+c on his script or just
            # lost his connection. socket.close() also invokes socket.shutdown(socket.SHUT_RDWR) what sends information
            # about closing the socket (shutdown read/write) and that's also a cause when we receive an empty message
            return ClientResponseTypes.CLIENT_DISCONNECTED, None, None, None, None

    def handle_incoming_messages(self) -> None:
        """
        Take incoming byte-strings and extract the header, based on which interpret and decode the message. Plug it in
        the appropriate-form dictionary and save to message handler.
        Valid client response codes:
            - 1001 - regular text message
            - 1002 - message received response
            - 1003 - everything ok (number of messages given by the server matches the one on the client side)
            - 1004 - missing message (a message gone missing)
            - 1005 - username
            - 1006 - passcode
        :return:
        """

        self.log(
            ServerEventTypes.DEBUG,
            datetime.now(),
            func_name=self.handle_incoming_messages.__name__,
            message="Starting"
        )

        if self.debug:
            self.methods_called_debug.append("handle_incoming_messages")

        end_time = time() + TIMEOUT_SECONDS

        while not self.debug or time() < end_time:

            self.log(
                ServerEventTypes.DEBUG,
                datetime.now(),
                func_name=self.handle_incoming_messages.__name__,
                message="No sockets notified"
            )

            read_sockets, _, exception_sockets = select.select(self.sockets_list, [], self.sockets_list)

            self.log(
                ServerEventTypes.DEBUG,
                datetime.now(),
                func_name=self.handle_incoming_messages.__name__,
                message="One of the sockets is notified",
                read_sockets=read_sockets,
                exception_sockets=exception_sockets
            )

            # Iterate over notified sockets
            for notified_socket in read_sockets:

                self.log(
                    ServerEventTypes.DEBUG,
                    datetime.now(),
                    func_name=self.handle_incoming_messages.__name__,
                    message="Iterating over notified sockets"
                )

                # If notified socket is a server socket - new connection, accept it
                if notified_socket == self.server_socket:

                    self.log(
                        ServerEventTypes.DEBUG,
                        datetime.now(),
                        func_name=self.handle_incoming_messages.__name__,
                        message="Server socket is notified."
                    )

                    # Accept new connection. That gives us new socket - client socket, connected to this given client
                    # only and ip/port set.
                    client_socket, client_address = notified_socket.accept()

                    self.log(
                        ServerEventTypes.ATTEMPTED_CONNECTION,
                        datetime.now(),
                        client_addr=client_address
                    )

                else:

                    # Else, existing socket is notified
                    client_socket = notified_socket

                    self.log(
                        ServerEventTypes.DEBUG,
                        datetime.now(),
                        func_name=self.handle_incoming_messages.__name__,
                        message="Existing socket is notified",
                        client_socket=client_socket
                    )

                # Receive the message and break it down into header components and the message itself. Returned values
                # are decoded and converted to appropriate types (ClientResponseTypes, datetime, datetime, int, str). If
                # notification indicated that the client disconnected - i.e. 'empty' message was sent the 2nd through
                # 5th returned values are None.
                response_type, client_sent_at, server_received_at, message_length, message = self.receive_message(client_socket)

                self.log(
                    ServerEventTypes.DEBUG,
                    datetime.now(),
                    func_name=self.handle_incoming_messages.__name__,
                    message="...",
                )

                print(f"[SERVER - HIM] Reading notification {[response_type, client_sent_at, server_received_at, message_length, message]}")
                print(f"[SERVER - HIM] client_socket.getsockname(): {client_socket.getsockname()}")
                print(f"[SERVER - HIM] client_socket.getpeername(): {client_socket.getpeername()}")

                # Find user with given address, if none is found client was probably not approved to send messages
                username = next(
                    (
                        user["client_name"] for user in self.clients_list
                        if user["addr"] == client_socket.getpeername()
                    ),
                    None
                )

                if response_type in [
                        ClientResponseTypes.USERNAME_GIVEN.value,
                        ClientResponseTypes.PASSCODE_GIVEN.value,
                        ClientResponseTypes.CLIENT_DISCONNECTED.value
                ]:

                    print(f"[SERVER - HIM] Proceeding to handle_clients with {[client_socket, response_type, message]}.")

                    # call handle_clients - it will select a procedure based on the ClientResponseTypes
                    self.handle_clients(
                        client_socket=client_socket,
                        client_response_code=ClientResponseTypes(response_type),
                        client_message=message
                    )

                elif username:

                    if response_type == ClientResponseTypes.MISSING_MESSAGE.value:

                        print(f"[SERVER - HIM] Missing message!")

                        # call handle_missing_message
                        self.handle_missing_message()

                    elif response_type == ClientResponseTypes.REGULAR_TEXT_MESSAGE.value:

                        print(f"[SERVER - HIM] Regular text message from {username} {client_socket.getpeername()}")
                        print(f"[SERVER - HIM] Saving: header: {message_length}, client_name: {username}, "
                              f"timestamps.client_sent: {client_sent_at}, timestamps.server_received: "
                              f"{server_received_at}, message: {message}, client_address: {client_socket.getpeername()}"
                              f", broadcasted.client_name: {[user['client_name'] for user in self.clients_list if user['client_name'] != username]}")

                        self.client_messages.append_message(
                            message_id=None,
                            header=message_length,
                            client_name=username,
                            timestamps={
                                "client_sent": client_sent_at,
                                "server_received": server_received_at
                            },
                            message=message,
                            client_address=client_socket.getpeername(),
                            broadcasted=[{"client_name": user["client_name"]} for user in self.clients_list if user["client_name"] != username]
                        )

                        print(f"[SERVER - HIM] self.client_messages.waiting_messages: {self.client_messages.waiting_messages}")

                    elif response_type == ClientResponseTypes.MESSAGE_RECEIVED_RESPONSE.value:

                        print(f"[SERVER - HIM] MESSAGE_RECEIVED_RESPONSE from {username} {client_socket.getpeername()}")
                        print(f"[SERVER - HIM] Updating message with id = {message}")

                        # MESSAGE_RECEIVED_RESPONSE type of message has a following structure:
                        # 1002<message_sent_at><message_length><message_id>
                        self.client_messages.query(
                            "UPDATE broadcasted.message_received_at={} WHERE message_id=={}, broadcasted.client_name=={}",
                            update_val=[client_sent_at],
                            where_val=[message, username]
                        )

                        print(f"[SERVER - HIM] Message updated: {self.client_messages.query('GET WHERE message_id=={}', where_val=message)}")

                    elif response_type == ClientResponseTypes.EVERYTHING_OK:

                        print(f"[SERVER - HIM] EVERYTHING_OK from {client_socket.getpeername()}")

                        continue

                    else:

                        print(f"[SERVER - HIM] Wrong response code from {client_socket.getpeername()}")

                        # wrong/no response code - log it
                        continue

                else:

                    print(f"[SERVER - HIM] Unapproved client tried to send a message.")

                    # log that unapproved client tried to send a message
                    continue

    def __send_messages(self, message_handler_object: MessageHandler, message_type: Literal['client', 'server']):

        if self.debug:
            self.methods_called_debug.append("__send_messages")

        # Iterate over all not sent messages
        for msg in message_handler_object.query("GET WHERE broadcasted.message_sent_at=={}", where_val=[None]):

            print(f"[SERVER - MD] Found message(s) to be send.")
            print(f"[SERVER - MD] msg['broadcasted'] = {msg['broadcasted']}")
            print(f"[SERVER - MD] self.clients_list = {self.clients_list}")

            # Iterate over all clients
            for client in msg["broadcasted"]:

                print(f"[SERVER - MD] client_name = {client['client_name']}")
                print(f"[SERVER - MD] type(client_name) = {type(client['client_name'])}")

                # Check if the client_name is bytes, i.e. is it client registered in the clients_list
                if isinstance(client["client_name"], bytes):

                    # Convert to tuple
                    addr = pickle.loads(client["client_name"])

                    print(f"[SERVER - MD] addr = {addr}")

                    # Grab the client socket by the address
                    recipient_client_socket = next((soc for soc in self.sockets_list[1:] if soc.getpeername() == addr), None)

                else:

                    # Grab username and addr if the client is still connected, else None
                    client_data = next((c for c in self.clients_list if c["client_name"] == client["client_name"]), None)

                    if client_data:

                        # Grab the client socket by the address
                        recipient_client_socket = next((soc for soc in self.sockets_list[1:] if soc.getpeername() == client_data["addr"]), None)

                    else:

                        recipient_client_socket = None

                print(f"[SERVER - MD] recipient_client_socket = {recipient_client_socket}")

                # Check if the client is still connected
                if recipient_client_socket:

                    print("[SERVER - MD] Client still connected.")
                    print(f"[SERVER - MD] recipient_client_socket = {recipient_client_socket}")

                    # Send the message
                    if message_type == 'server':

                        print(f"[SERVER - MD] Sending {msg['response_type'].value}")

                        recipient_client_socket.send(f"{msg['response_type'].value}{msg['info']}".encode(FORMAT))

                    else:

                        print(f"[SERVER - MD] Sending {ClientResponseTypes.REGULAR_TEXT_MESSAGE.value}"
                              f"{msg['message_id']}{len(msg['message'])}...{msg['message']}")

                        recipient_client_socket.send(f"{ClientResponseTypes.REGULAR_TEXT_MESSAGE.value}"
                                                     f"{msg['message_id']}"
                                                     f"{len(msg['message']):<{MESSAGE_LENGTH_HEADER_LENGTH}}"
                                                     f"{msg['message']}".encode(FORMAT))

                    # Set message_sent_at timestamp
                    message_handler_object.query(
                        "UPDATE broadcasted.message_sent_at={} WHERE message_id=={}, broadcasted.message_sent_at=={}",
                        update_val=[datetime.now()],
                        where_val=[msg['message_id'], None]
                    )

    def message_dispatcher(self, *, __timeout: int = 0, __sleep_seconds: int = 1) -> None:
        """
        Dispatch messages that were not sent yet.
        :return:
        """

        self.log(
            ServerEventTypes.DEBUG,
            datetime.now(),
            func_name=self.message_dispatcher.__name__,
            message="Starting"
        )

        if self.debug:
            self.methods_called_debug.append("message_dispatcher")

        end_time = time() + __timeout if __timeout != 0 else TIMEOUT_SECONDS

        while not self.debug or time() < end_time:

            # First deal with server-to-client messages
            self.__send_messages(self.server_messages, 'server')

            # Deal with client-to-client messages
            self.__send_messages(self.client_messages, 'client')

            if self.debug:
                sleep(__sleep_seconds)

    def log(self, server_event_type: ServerEventTypes, timestamp: datetime, **kwargs) -> None:
        """
        Log every event (server start/stop, client connected/disconnected, message received/sent by the server,
        message received by the client) and save as a text file. The format of each line should be:
            datetime event message
        Example:
            2022-11-26 12:35:15.004325 [STARTING] Server is booting up...
            2022-11-26 12:35:15.004962 [LISTENING] Server is listening on 127.0.0.1:5050
            2022-11-26 12:35:16.112854 [NEW CONNECTION] New connection accepted from 127.235.48.2:67912 as 'john1985'
            2022-11-26 12:35:16.126326 [ACTIVE CONNECTIONS] Currently connected: ['john1985']
            ...
        Suggested event types and information passed on to the message:
            - STARTING - None
            - STARTED - run-time variables and their values (CLIENT_LIMIT = 2),
            - LISTENING - server ip, server port
            - ATTEMPTED CONNECTION - client ip, client port, Accepted/Rejected (Correct/Wrong passcode or other reason)
            - NEW CLIENT - client ip, client port, client name
            - ACTIVE CLIENTS - all active client names
            - CLIENT DISCONNECTED - client ip, client port, client name
            - MESSAGE RECEIVED - sender ip, sender port, sender name, message id
            - MESSAGE DISPATCHED - recipient ip, recipient port, recipient name, message id
            - MESSAGED DELIVERED - recipient name, message id
            - SHUTTING DOWN - None
        :param kwargs: various kwargs (<any run-time vars>, 'client_addr', etc...)
        :param timestamp: datetime of the event
        :param server_event_type: member of ServerEventTypes Enum class
        :return:
        """
        if self.debug:
            self.methods_called_debug.append("log")

        line_beginning = f"{timestamp} [{server_event_type.value()}] "

        match server_event_type:
            case ServerEventTypes.STARTING:
                message = f"Server is booting up..."

            case ServerEventTypes.STARTED:
                message = f"Run-time variables and their values: {(key + '=' + str(val) + ', ' for key, val in kwargs.items())}"

            case ServerEventTypes.LISTENING:
                message = f"Server is listening on {self.addr}"

            case ServerEventTypes.ATTEMPTED_CONNECTION:
                try:
                    message = f"Attempted connection from {kwargs['client_addr']}"
                except KeyError:
                    raise KeyError("'client_addr' key argument required.")

            case ServerEventTypes.NEW_SOCKET:
                try:
                    message = f"New socket: {kwargs['client_socket']}"
                except KeyError:
                    raise KeyError("'client_socket' key argument required.")

            case ServerEventTypes.NEW_CLIENT:
                try:
                    message = f"New client: {kwargs['client_name']} {kwargs['client_addr']}"
                except KeyError:
                    raise KeyError("'client_name', 'client_addr' key arguments required.")

            case ServerEventTypes.ACTIVE_SOCKETS:
                message = f"Active sockets: {self.sockets_list}"

            case ServerEventTypes.ACTIVE_CLIENTS:
                message = f"Active clients: {self.clients_list}"

            case ServerEventTypes.CLIENT_DISCONNECTED:
                try:
                    message = f"Client disconnected: {kwargs['client_name']} {kwargs['client_addr']}"
                except KeyError:
                    raise KeyError("'client_name', 'client_addr' key arguments required.")

            case ServerEventTypes.SERVER_RESPONSE:
                try:
                    message = f"Client message ID: {kwargs['message_id']}, server response: " \
                              f"{kwargs['server_response_type']}"
                except KeyError:
                    raise KeyError("'message_id', 'server_response_type' key arguments required.")

            case ServerEventTypes.MESSAGE_RECEIVED:
                try:
                    message = f"New message from {kwargs['client_name']} {kwargs['client_addr']}: " \
                              f"[{kwargs['client_response_type']}, {kwargs['message_sent_at']}] " \
                              f"{kwargs['message_content']} (ID: {kwargs['message_id']})"
                except KeyError:
                    raise KeyError("'client_name', 'client_addr', 'client_response_type', 'message_sent_at', "
                                   "'message_content', 'message_id' key arguments required.")

            case ServerEventTypes.MESSAGE_DISPATCHED:
                try:
                    message = f"Client message ID: {kwargs['client_message_id']}, server response: " \
                              f"{kwargs['server_response_type']}, server message id: {kwargs['server_message_id']}"
                except KeyError:
                    raise KeyError("'client_message_id', 'server_response_type', 'server_message_id' key arguments "
                                   "required.")

            case ServerEventTypes.MISSING_MESSAGE:
                message = ""

            case ServerEventTypes.SHUTTING_DOWN:
                message = f"Server is shutting down..."

            case ServerEventTypes.DEBUG:
                try:
                    if 'message' in kwargs.keys():
                        message = f"({kwargs['func_name']}) {kwargs['message']}"
                    else:
                        message = f"({kwargs['func_name']}) {(key + '=' + str(val) for key, val in kwargs.items() if key != 'func_name')}"
                except KeyError:
                    raise KeyError("'func_name' key argument required.")

            case _:
                raise ValueError('Unrecognised value of server_event_type.')

        if self.debug:

            print(line_beginning + message)

        else:

            # check if the 'log' directory exists
            if not os.path.exists(project_path / 'log'):

                # create a log dir
                os.mkdir(project_path / 'log')

            # check if the file exists in the log directory
            if not os.path.exists(project_path / f"log/{self.log_filename}"):

                # it does not, create a new one
                with open(project_path / self.log_filename, 'x') as _:
                    pass

            # write (append) the line to the log file
            with open(project_path / self.log_filename, 'a') as f:

                f.write(line_beginning + message)


if __name__ == "__main__":
    server = Server()

    handle_incoming_messages_thread = Thread(target=server.handle_incoming_messages)
    handle_incoming_messages_thread.start()

    message_dispatcher_thread = Thread(target=server.message_dispatcher)
    message_dispatcher_thread.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def client_send(client_response, msg):

        message = f"{client_response.value}" \
                  f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}" \
                  f"{len(msg):<{MESSAGE_LENGTH_HEADER_LENGTH}}" \
                  f"{msg}"

        print(f"[CLIENT] Sent message: {message.replace(' ', '')}")

        client.send(message.encode('utf-8'))

        response = client.recv(RESPONSE_TYPE_HEADER_LENGTH)

        print(f"[CLIENT] Message received: {response.decode(FORMAT)}")

    while True:
        try:
            client.connect((server.get_addr()))

            print(f"[CLIENT] Found connection at {server.get_addr()}")

        except Exception:

            pass

        else:

            passcode = server.get_passcode()

            client_send(ClientResponseTypes.PASSCODE_GIVEN, passcode)

            username = "some_username"

            client_send(ClientResponseTypes.USERNAME_GIVEN, username)

            some_message = "Hello world!"

            client_send(ClientResponseTypes.REGULAR_TEXT_MESSAGE, some_message)

    # #      SERVER      #
    #
    # server_private_key = PrivateKey.generate()
    # server_public_key = server_private_key.public_key
    #
    # #      CLIENT      #
    #
    # client_private_key = PrivateKey.generate()
    # client_public_key = client_private_key.public_key
    #
    # # after passcode validation server sends its public key which client who wants to send a message uses to encrypt it
    # # (we skip the username part for now)
    # client_box = SealedBox(server_public_key)
    #
    # message = "Hello server!"
    # encrypted_message = client_box.encrypt(message.encode('utf-8'))
    #
    # #      SERVER      #
    #
    # server_box = SealedBox(server_private_key)
    # msg = server_box.decrypt(encrypted_message)
    #
    # flag = False
    # flag_m = pickle.dumps(flag)
    # if not pickle.loads(flag_m):
    #     print(flag_m)
