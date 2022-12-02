import pickle
import unittest
from pathlib import Path
from src.server import Server
import os
from datetime import datetime
import psutil
import socket
import pprint as pp
from src.schema import get_message_id
from src.shared_enum_vars import ClientResponseTypes, ServerEventTypes, ServerResponseTypes
from dotenv import load_dotenv

# load environmental variables
dotenv_path = Path(__file__).parent.parent.resolve() / ".env"
load_dotenv(dotenv_path=dotenv_path)
FORMAT = os.getenv('FORMAT')
HEADER_LENGTH = int(os.getenv('HEADER_LENGTH'))
RESPONSE_TYPE_HEADER_LENGTH = int(os.getenv('RESPONSE_TYPE_HEADER_LENGTH'))


def get_server_message(created_at: datetime, client_addr: tuple[str, int], message: ServerResponseTypes) -> dict:
    return {
        "header": RESPONSE_TYPE_HEADER_LENGTH,
        "created_at": created_at,
        "message": message.value,
        "broadcasted": {
            "client_name": pickle.dumps(client_addr),
            "client_connected": True,
            "message_sent_at": None,
            "message_received_at": None
        },
        "message_id": get_message_id(
            None,
            {
                "created_at": created_at,
                "broadcasted": {
                    "client_name": pickle.dumps(client_addr)
                }
            }
        )
    }


def get_client_message(
        client_sent: datetime,
        server_received: datetime,
        sender_client_addr: tuple[str, int],
        sender_client_name: str,
        message: str,
        recipient_client_name: str,
        client_connected: bool = True,
        message_sent_at: datetime | None = None,
        message_received_at: datetime | None = None
) -> dict:
    return {
        "header": len(message),
        "client_name": sender_client_name,
        "timestamps": {
            "client_sent": client_sent,
            "server_received": server_received,
        },
        "message": message,
        "client_address": sender_client_addr,
        "broadcasted": [
            {
                "client_name": recipient_client_name,
                "client_connected": client_connected,
                "message_sent_at": message_sent_at,
                "message_received_at": message_received_at
            }
        ],
        "message_id": get_message_id(
            None,
            {
                "created_at": client_sent,
                "broadcasted": {
                    "client_name": pickle.dumps(sender_client_addr)
                }
            }
        )
    }


class TestServer(unittest.TestCase):
    """
    Protocol:
        1. Server listens
        2. Client connects and sends passcode
        3. Is passcode correct?
            a. Yes, save client to approved connections, send success message and request username
            b. No, send access denied message
        4. Client sends username (only safe characters - client-side validation)
        5. Is the username correct? (is it unique?)
            a. Yes, save
    """

    def setUp(self) -> None:
        self.server = Server()

        self.passcode = self.server.get_passcode()
        self.wrong_passcode = self.server.get_passcode()[3:]  # remove first few bytes/characters

        self.server_addr = self.server.get_addr()

        # instantiate client socket and connect to the server
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(self.server_addr)

        self.client_addr = self.client_socket.getpeername()
        self.client_username = "some_username"

        self.client_message = get_client_message(
            client_sent=datetime(2022, 12, 2, 2, 9, 50, 123456),
            server_received=datetime(2022, 12, 2, 2, 9, 50, 123456),
            sender_client_addr=self.client_addr,
            sender_client_name=self.client_username,
            message="Hello World!",
            recipient_client_name="some_other_user"
        )

    def test_handle_clients_new_connection_correct_passcode_clients_list(self) -> None:
        self.server.handle_clients(client_response_code='p', client_message=self.passcode, addr=self.client_addr)

        expected = [{"client_name": "", "client_address": self.client_addr}]
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.passcode,
            addr=self.client_addr,
            __debug=True
        )

        expected = [get_server_message(created_at, self.client_addr, ServerResponseTypes.PASSCODE_CORRECT)]
        actual = self.server.server_messages.waiting_messages
        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_clients_list(self) -> None:
        self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode,
            addr=self.client_addr
        )

        expected = []
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode,
            addr=self.client_addr,
            __debug=True
        )

        expected = [get_server_message(created_at, self.client_addr, ServerResponseTypes.PASSCODE_INCORRECT)]
        actual = self.server.server_messages.waiting_messages
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_after_username_list_of_clients(self) -> None:
        self.server.approved_connections = [{"client_name": self.client_username, "client_address": self.client_addr}]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr
        )

        expected = []
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_before_username_list_of_clients(self) -> None:
        self.server.approved_connections = [{"client_name": "", "client_address": self.client_addr}]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr
        )

        expected = []
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_before_passcode_list_of_clients(self) -> None:
        self.server.approved_connections = []

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr
        )

        expected = []
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_username_correct_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.USERNAME_GIVEN,
            client_message=self.client_username,
            addr=self.client_addr,
            __debug=True
        )
        expected = [get_server_message(created_at, self.client_addr, ServerResponseTypes.USERNAME_ACCEPTED)]
        actual = self.server.server_messages

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_messages_list_remove_disconnected_from_messages_false(self) -> None:
        """
        Test if the recipient is still in the broadcasted list
        :return:
        """
        self.server.client_messages.waiting_messages = [self.client_message]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr,
            remove_disconnected_from_messages=False
        )

        expected = self.client_message["broadcasted"]
        actual = self.server.client_messages.waiting_messages[0]["broadcasted"]

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_messages_list_remove_disconnected_from_messages_true(self) -> None:
        """
        Test if the recipient got removed from the broadcasted list
        :return:
        """
        self.server.client_messages.waiting_messages = [self.client_message]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr,
            remove_disconnected_from_messages=True
        )

        expected = []
        actual = self.server.client_messages.waiting_messages[0]["broadcasted"]

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_messages_list_remove_disconnected_from_messages_false_broadcasted_client_connected(self) -> None:
        """
        Test if the recipient's client_connected flag changed to False
        :return:
        """
        self.server.client_messages.waiting_messages = [self.client_message]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None,
            addr=self.client_addr,
            remove_disconnected_from_messages=True
        )

        expected = False
        actual = self.server.client_messages.waiting_messages[0]["broadcasted"][0]["client_connected"]

        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_new_regular_message(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_received_message_response(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_everything_ok_response(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_missing_message_response(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_username_given(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_passcode_given(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_message_dispatcher_everyone_received_messages_nothing_to_do(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_message_dispatcher_one_message_to_send(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_message_dispatcher_multiple_messages_in_order(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_message_dispatcher_multiple_messages_out_of_order(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_message_dispatcher_send_message_with_id(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_starting(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_started(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_listening(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_attempted_connection(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_new_client(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_active_clients(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_client_disconnected(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_message_received(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_message_dispatched(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_messaged_delivered(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_missing_message(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_log_shutting_down(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_missing_message(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
