import codecs

from dotenv import load_dotenv
from typing import Literal
from enum import Enum
from secrets import token_hex
from nacl.public import PrivateKey, SealedBox


class ClientResponseCodes(Enum):
    REGULAR_TEXT_MESSAGE = 'm'
    MESSAGE_RECEIVED_RESPONSE = 'r'
    EVERYTHING_OK = 'k'
    MISSING_MESSAGE = 'x'
    USERNAME_GIVEN = 'u'
    PASSCODE_GIVEN = 'p'


class ServerEventTypes(Enum):
    STARTING = "STARTING"
    STARTED = "STARTED"
    LISTENING = "LISTENING"
    ATTEMPTED_CONNECTION = "ATTEMPTED_CONNECTION"
    NEW_CLIENT = "NEW_CLIENT"
    ACTIVE_CLIENTS = "ACTIVE_CLIENTS"
    CLIENT_DISCONNECTED = "CLIENT_DISCONNECTED"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    MESSAGE_DISPATCHED = "MESSAGE_DISPATCHED"
    MESSAGED_DELIVERED = "MESSAGED_DELIVERED"
    MISSING_MESSAGE = "MISSING_MESSAGE"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class Server:
    def __init__(self):
        pass

    # TODO:
    #  1. set up server
    #  2. listen for incoming connections
    #  3. record connecting/disconnecting clients (add to message stack and list of clients)
    #  4. if client sent a message add it to the stack
    #  5. send messages from the stack to clients who did not receive those messages
    #  6. log every action (server start/stop, client connected/disconnected, message received/sent by the server,
    #  message received by the client) and save as a text file
    #  7*. How do we know that the client did not receive one of the messages? Let us have different UserStatus schema:
    #  client_name, client_connected, message_sent, message_received. message_dispatcher() will send out message with
    #  message_sent set to False unless specified to send a message with specified ID - it will set message_sent to True
    #  whenever it sends the message. handle_incoming_messages() will deal with the other flag (message_received). It
    #  will set it to True whenever a 'message received response' is received by the server. Another possible case is
    #  when one of the messages sent by the server is gone missing. The missing message shall be found by it's
    #  message_received flag and re-issued.
    #
    # NOTE: handle_incoming_messages and message_dispatcher operate in separate threads.
    #  handle_incoming_messages  can call  receive_message, handle_clients, handle_missing_message

    def get_passcode(self) -> str:
        """
        Return generated passcode to the console - user then can copy it and give it to whomever he wants to message
        with.
        :return:
        """
        return self.passcode

    def handle_clients(
            self,
            *, client_response_code: Literal[ClientResponseCodes.USERNAME_GIVEN, ClientResponseCodes.PASSCODE_GIVEN],
            remove_disconnected: bool = False,
    ) -> None:
        """
        Handle users that are joining the chat room. Validate passcodes and if correct, add clients to the list of
        connected clients or remove if their dropped out. Record appropriate messages in the message pool - these are to
        be sent out to other connected clients. Alter 'message.broadcasted' or 'message.broadcasted.user_connected'
        value accordingly.
        :return:
        """
        pass

    def handle_missing_message(self) -> None:
        """

        :return:
        """
        pass

    def handle_incoming_messages(self) -> None:
        """
        Take incoming byte-strings and extract the header, based on which interpret and decode the message. Plug it in
        the appropriate-form dictionary and save to message handler.
        Valid client response codes:
            - m - regular text message
            - r - message received response
            - k - everything ok (number of messages given by the server matches the one on the client side)
            - x - missing message (a message gone missing)
            - u - username
            - p - passcode
        :return:
        """
        pass

    def message_dispatcher(self, message_id: str | None = None) -> None:
        """
        Dispatch messages that were not sent yet or - if message_id given - send message with given ID.
        :return:
        """
        pass

    def log(self, server_event_type: ServerEventTypes) -> None:
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
        :return:
        """
        pass


if __name__ == "__main__":

    #      SERVER      #

    server_private_key = PrivateKey.generate()
    server_public_key = server_private_key.public_key

    print(server_public_key.__bytes__().decode('utf-8'))  # UnicodeDecodeError

    #      CLIENT      #

    client_private_key = PrivateKey.generate()
    client_public_key = client_private_key.public_key

    # after passcode validation server sends its public key which client who wants to send a message uses to encrypt it
    # (we skip the username part for now)
    client_box = SealedBox(server_public_key)

    message = "Hello server!"
    encrypted_message = client_box.encrypt(message.encode('utf-8'))

    #      SERVER      #

    server_box = SealedBox(server_private_key)
    msg = server_box.decrypt(encrypted_message)

    # print(msg.decode('utf-8'))
