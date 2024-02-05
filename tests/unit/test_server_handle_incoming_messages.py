import unittest
import socket
from threading import Thread
from time import time
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

from src.server import Server
from src.shared_enum_vars import ClientResponseTypes
from src.schema import get_message_id

project_path = Path(__file__).parent.parent.resolve()
load_dotenv(dotenv_path=project_path / ".env")

FORMAT = os.getenv('FORMAT')
RESPONSE_TYPE_HEADER_LENGTH = int(os.getenv('RESPONSE_TYPE_HEADER_LENGTH'))
TIMESTAMP_HEADER_LENGTH = int(os.getenv('TIMESTAMP_HEADER_LENGTH'))
MESSAGE_ID_HEADER_LENGTH = int(os.getenv('MESSAGE_ID_HEADER_LENGTH'))
MESSAGE_LENGTH_HEADER_LENGTH = int(os.getenv('MESSAGE_LENGTH_HEADER_LENGTH'))
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS'))


class TestServerHandleIncomingMessages(unittest.TestCase):
    def setUp(self) -> None:
        # Spin up the server
        self.server = Server(_Server__debug=True)
        self.server_addr = self.server.get_addr()

        # Get the correct passcode
        self.passcode = self.server.get_passcode()

        local_ip = socket.gethostbyname(socket.gethostname())

        # Instantiate clients sockets and bind to the ip/port
        self.client_socket_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket_1.bind((local_ip, 0))
        self.client_socket_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket_2.bind((local_ip, 0))

        # Get details about clients
        self.client_addr_1 = self.client_socket_1.getsockname()
        self.client_username_1 = "client1"
        self.client_addr_2 = self.client_socket_2.getsockname()
        self.client_username_2 = "client2"

        # Add clients to the sockets and clients lists
        self.server.sockets_list += [self.client_socket_1, self.client_socket_2]
        self.server.clients_list = [
            {"client_name": self.client_username_1, "addr": self.client_addr_1},
            {"client_name": self.client_username_2, "addr": self.client_addr_2}
        ]

    def test_handle_incoming_messages_regular_text_message(self) -> None:

        # run the handle_incoming_messages function in a thread
        handle_incoming_messages_thread = Thread(target=self.server.handle_incoming_messages)
        handle_incoming_messages_thread.start()

        client_sent = datetime.now()
        self.client_socket_1.connect(self.server_addr)
        self.client_socket_1.send(f"{ClientResponseTypes.REGULAR_TEXT_MESSAGE.value}"
                                  f"{client_sent.strftime('%Y%m%d%H%M%S%f')}"
                                  f"{len('foo'):<{MESSAGE_LENGTH_HEADER_LENGTH}}"
                                  f"foo".encode(FORMAT))

        end_time = time() + TIMEOUT_SECONDS

        while time() < end_time:
            if self.server.client_messages.waiting_messages:
                expected = [
                    {
                        "header": len('foo'),
                        "client_name": self.client_username_1,
                        "timestamps": {
                            "client_sent": client_sent,
                        },
                        "message": 'foo',
                        "client_address": self.client_addr_1,
                        "broadcasted": [
                            {
                                "client_name": self.client_username_2,
                                "message_sent_at": None,
                                "message_received_at": None
                            }
                        ],
                        "message_id": get_message_id(
                            None,
                            {
                                "timestamps": client_sent,
                                "client_address": self.client_addr_1
                            }
                        )
                    }
                ]  # removed timestamps.server_received

                actual = self.server.client_messages.waiting_messages

                self.assertEqual(1, len(actual))
                self.assertIn("timestamps", actual[0].keys())
                self.assertIn("server_received", actual[0]["timestamps"].keys())

                del actual[0]["timestamps"]["server_received"]

                self.assertEqual(expected, actual)

                break

        else:

            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_message_received_response(self) -> None:
        # run the handle_incoming_messages function in a thread
        handle_incoming_messages_thread = Thread(target=self.server.handle_incoming_messages)
        handle_incoming_messages_thread.start()

        time_diff = timedelta(seconds=1)
        client_sent = datetime.now()
        server_received = client_sent + time_diff
        server_sent = server_received + time_diff
        client_received = server_sent + time_diff
        message_id = get_message_id(None, {"timestamps": client_sent, "client_address": self.client_addr_1})

        self.server.client_messages.waiting_messages = [
            {
                "header": MESSAGE_ID_HEADER_LENGTH,
                "client_name": self.client_username_1,
                "timestamps": {
                    "client_sent": client_sent,
                    "server_received": server_received
                },
                "message": 'foo',
                "client_address": self.client_addr_1,
                "broadcasted": [
                    {
                        "client_name": self.client_username_2,
                        "message_sent_at": server_sent,
                        "message_received_at": None
                    }
                ],
                "message_id": message_id
            }
        ]

        self.client_socket_2.connect(self.server_addr)
        self.client_socket_2.send(f"{ClientResponseTypes.MESSAGE_RECEIVED_RESPONSE.value}"
                                  f"{client_received.strftime('%Y%m%d%H%M%S%f')}"
                                  f"{MESSAGE_ID_HEADER_LENGTH:<{MESSAGE_LENGTH_HEADER_LENGTH}}"
                                  f"{message_id}".encode(FORMAT))

        end_time = time() + TIMEOUT_SECONDS

        while time() < end_time:
            if self.server.client_messages.waiting_messages[0]["broadcasted"][0]["message_received_at"] is not None:

                expected = self.server.client_messages.waiting_messages
                expected[0]["broadcasted"][0]["message_received_at"] = client_received

                actual = self.server.client_messages.waiting_messages

                self.assertEqual(1, len(actual))

                self.assertEqual(expected, actual)

                break

        else:

            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_username_given(self) -> None:
        pass

    def test_handle_incoming_messages_passcode_given(self) -> None:
        pass

    def test_handle_incoming_messages_client_disconnected_before_passcode(self) -> None:
        pass

    def test_handle_incoming_messages_client_disconnected_after_passcode(self) -> None:
        pass

    def test_handle_incoming_messages_client_disconnected_after_client_name(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
