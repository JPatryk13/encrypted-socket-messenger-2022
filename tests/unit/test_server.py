import pickle
import threading
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
import random
from time import time

# load environmental variables
project_path = Path(__file__).parent.parent.parent.resolve()
load_dotenv(dotenv_path=project_path / ".env")

FORMAT = os.getenv('FORMAT')
MESSAGE_LENGTH_HEADER_LENGTH = int(os.getenv('MESSAGE_LENGTH_HEADER_LENGTH'))
RESPONSE_TYPE_HEADER_LENGTH = int(os.getenv('RESPONSE_TYPE_HEADER_LENGTH'))
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS'))


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


def format_client_message(response_type: ClientResponseTypes, message: str, client_sent_at: datetime) -> str:
    return response_type.value + f"{len(message):<{MESSAGE_LENGTH_HEADER_LENGTH}}" + client_sent_at.strftime("%Y%m%d%H%M%S%f") + message



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
        self.log_current_date = datetime(2022, 12, 4, 22, 59, 15, 9274)
        self.server = Server(_Server__debug=True, _Server__log_file_created_at=self.log_current_date)

        self.passcode = self.server.get_passcode()
        self.wrong_passcode = self.server.get_passcode()[3:]  # remove first few bytes/characters

        self.server_addr = self.server.get_addr()

        # instantiate client socket and connect to the server
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(self.server_addr)

        # get details about the client
        self.client_addr = self.client_socket.getpeername()
        self.client_username = "some_username"

        # render a sample message that a client could send
        self.client_message = get_client_message(
            client_sent=datetime(2022, 12, 2, 2, 9, 50, 123456),
            server_received=datetime(2022, 12, 2, 2, 9, 50, 123456),
            sender_client_addr=self.client_addr,
            sender_client_name=self.client_username,
            message="Hello World!",
            recipient_client_name="some_other_user"
        )

        # randomise ip and port for sample fake client and generate fake_client_username
        self.random_ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
        self.random_port = random.randint(1000, 7000)
        self.fake_client_username = "fake_client_username"

        # list of messages (conversation between self.client_socket and fake client) - all messages were dispatched by
        # the server and received by each client
        self.message_list = [
            get_client_message(
                client_sent=datetime(2022, 12, 2, 2, i, 36, 123456),
                server_received=datetime(2022, 12, 2, 2, i, 38, 123456),
                sender_client_addr=self.client_addr if bool(i % 2) else (self.random_ip, self. random_port),
                sender_client_name=self.client_username if bool(i % 2) else self.fake_client_username,
                message=f"Message #{i + 1}",
                recipient_client_name=self.fake_client_username if bool(i % 2) else self.client_username,
                client_connected=True,
                message_sent_at=datetime(2022, 12, 2, 2, i, 40, 123456),
                message_received_at=datetime(2022, 12, 2, 2, i, 42, 123456)
            ) for i in range(10)
        ]

        self.log_file_path = project_path / "log"
        self.log_filenames = []
        self.log_current_date_str = "2022-12-04 22:59:15.009274"
        self.sample_log_filename = "log_" + self.log_current_date.strftime("%Y%m%d%H%M%S%f") + ".txt"

    def tearDown(self) -> None:
        if self.log_filenames:
            for filename in self.log_filenames:
                os.remove(self.log_file_path / filename)

    def test_handle_clients_new_connection_correct_passcode_clients_list(self) -> None:
        self.server.handle_clients(client_response_code='p', client_message=self.passcode)

        expected = [{"client_name": "", "client_address": self.client_addr}]
        actual = self.server.sockets_list

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.passcode
        )

        expected = [get_server_message(created_at, self.client_addr, ServerResponseTypes.PASSCODE_CORRECT)]
        actual = self.server.server_messages.waiting_messages
        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_clients_list(self) -> None:
        self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode
        )

        expected = []
        actual = self.server.sockets_list

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode
        )

        expected = [get_server_message(created_at, self.client_addr, ServerResponseTypes.PASSCODE_INCORRECT)]
        actual = self.server.server_messages.waiting_messages
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_after_username_list_of_clients(self) -> None:
        self.server.approved_connections = [{"client_name": self.client_username, "client_address": self.client_addr}]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        expected = []
        actual = self.server.sockets_list

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_before_username_list_of_clients(self) -> None:
        self.server.approved_connections = [{"client_name": "", "client_address": self.client_addr}]

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        expected = []
        actual = self.server.sockets_list

        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_before_passcode_list_of_clients(self) -> None:
        self.server.approved_connections = []

        self.server.handle_clients(
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        expected = []
        actual = self.server.sockets_list

        self.assertEqual(expected, actual)

    def test_handle_clients_username_correct_messages_list(self) -> None:
        created_at = self.server.handle_clients(
            client_response_code=ClientResponseTypes.USERNAME_GIVEN,
            client_message=self.client_username
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
            client_message=None
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
            client_message=None
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
            client_message=None
        )

        expected = False
        actual = self.server.client_messages.waiting_messages[0]["broadcasted"][0]["client_connected"]

        self.assertEqual(expected, actual)

    def test_handle_incoming_messages_new_regular_message(self) -> None:

        # list contains self.client and the self.client_message recipient name with randomised port and ip
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            },
            {
                "client_name": self.client_message["broadcasted"][0]["client_name"],
                "client_address": (self.random_ip, self.random_port)
            }
        ]

        # run handle_incoming_messages() in a separate threat with execute_once set to True to shut down after receiving
        # one message
        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        # send message from the client_socket with given client_sent_at
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.REGULAR_TEXT_MESSAGE,
                self.client_message["message"],
                self.client_message["client_sent"]
            ).encode(FORMAT)
        )

        expected = self.client_message

        # remove server_received key - it is defined at run-time inside the thread and will be unknown
        del expected["server_received"]

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                messages_list = self.server.client_messages.waiting_messages

                # if any message found perform tests
                if messages_list:

                    actual = messages_list[0]

                    # verify if the server_received key is in the message and remove it
                    self.assertIn("server_received", list(actual.keys()))
                    del actual["server_received"]

                    self.assertEqual(expected, actual)

                    break

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_received_message_response(self) -> None:
        # here the client with randomised ip and port number is the sender while self.client_socket is the recipient
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            },
            {
                "client_name": self.client_message["broadcasted"][0]["client_name"],
                "client_address": (self.random_ip, self.random_port)
            }
        ]

        # generate message that has been sent from the fake client, sent from the server and is to be received
        self.server.client_messages.waiting_messages = [
            get_client_message(
                client_sent=datetime.now(),
                server_received=datetime.now(),
                sender_client_addr=(self.random_ip, self.random_port),
                sender_client_name=self.fake_client_username,
                message="Hello World!",
                recipient_client_name=self.client_username,
                message_sent_at=datetime.now()
            )
        ]

        # run handle_incoming_messages() in a separate threat with execute_once set to True to shut down after receiving
        # one message
        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        message_received_at = datetime.now()

        # send message received response from the client_socket with message_received_at date
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.MESSAGE_RECEIVED_RESPONSE,
                "",
                message_received_at
            ).encode(FORMAT)
        )

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                expected = message_received_at
                actual = self.server.client_messages.waiting_messages[0]["broadcasted"][0]["message_received_at"]

                self.assertEqual(expected, actual)

                break

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_everything_ok_response(self) -> None:
        # populate approved_connections to avoid any errors
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            }
        ]

        # run handle_incoming_messages() in a separate threat with execute_once set to True to shut down after receiving
        # one message
        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        # send message received response from the client_socket with message_received_at date
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.EVERYTHING_OK,
                "",
                datetime.now()
            ).encode(FORMAT)
        )

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                what_has_been_run = self.server.methods_called_debug

                if what_has_been_run:

                    expected = what_has_been_run
                    actual = [Server.handle_incoming_messages.__name__]

                    self.assertEqual(expected, actual)

                    break

                else:

                    self.fail("what_has_been_run is empty.")

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    @unittest.skip("Client no longer is responsible for figuring out if there is any message missing and so is "
                   "handle_incoming_messages() function.")
    def test_handle_incoming_messages_missing_message_response(self) -> None:
        pass

    def test_handle_incoming_messages_username_given(self) -> None:
        # client was approved but did not send username yet - populate to avoid errors
        self.server.approved_connections = [
            {
                "client_name": "",
                "client_address": self.client_addr
            }
        ]

        # run handle_incoming_messages() in a separate threat with execute_once set to True to shut down after receiving
        # one message
        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        # send message received response from the client_socket with message_received_at date
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.USERNAME_GIVEN,
                self.client_username,
                datetime.now()
            ).encode(FORMAT)
        )

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                what_has_been_run = self.server.methods_called_debug

                if what_has_been_run:

                    self.assertIn(Server.handle_clients.__name__, what_has_been_run)

                    break

                else:

                    self.fail("what_has_been_run is empty.")

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_passcode_given(self) -> None:
        # start with no approved client - self.client_socket is yet to send the passcode
        self.server.approved_connections = []

        # run handle_incoming_messages() in a separate threat with execute_once set to True to shut down after receiving
        # one message
        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        # send message received response from the client_socket with message_received_at date
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.PASSCODE_GIVEN,
                "",  # empty passcode (we don't care if it's going to be approved or not)
                datetime.now()
            ).encode(FORMAT)
        )

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                what_has_been_run = self.server.methods_called_debug

                if what_has_been_run:

                    self.assertIn(Server.handle_clients.__name__, what_has_been_run)

                    break

                else:

                    self.fail("what_has_been_run is empty.")

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    def test_handle_incoming_messages_sort_messages(self) -> None:
        # all messages received and sent by the server and received by the client in random order besides 9th (1-10) in
        # the list the one sent by the client_socket
        msg_list = self.message_list[:-2] + [self.message_list[-1]]
        self.server.client_messages.waiting_messages = random.sample(msg_list, len(msg_list))

        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            }
        ]

        handle_incoming_messages_thread = threading.Thread(
            target=self.server.handle_incoming_messages,
            kwargs={
                "execute_once": True,
                "timeout": True
            }
        )
        handle_incoming_messages_thread.start()

        # send message received response from the client_socket with message_received_at date
        self.client_socket.send(
            format_client_message(
                ClientResponseTypes.REGULAR_TEXT_MESSAGE,
                self.message_list[-2]["message"],
                self.message_list[-2]["timestamps"]["client_sent"]
            ).encode(FORMAT)
        )

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished (received the message)
        while time() < end_time:

            if not handle_incoming_messages_thread.is_alive():

                expected = self.message_list

                # set to None - the newly received message
                expected[-2]["broadcasted"][0]["message_sent_at"] = None
                expected[-2]["broadcasted"][0]["message_received_at"] = None

                actual = self.server.client_messages.waiting_messages

                # remove timestamps.server_received as they will definitely be different
                del expected[-2]["timestamps"]["server_received"]
                del actual[-2]["timestamps"]["server_received"]

                self.assertEqual(expected, actual)

        else:
            # timeout
            self.fail("handle_incoming_messages() timed-out.")

    def test_message_dispatcher_everyone_received_messages_nothing_to_do(self) -> None:
        # all messages sent, all messages received
        self.server.client_messages.waiting_messages = self.message_list

        message_dispatcher_thread = threading.Thread(
            target=self.server.message_dispatcher,
            kwargs={
                "execute_once": True
            }
        )
        message_dispatcher_thread.start()

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if the thread is finished
        while time() < end_time:

            if not message_dispatcher_thread.is_alive():

                what_has_been_run = self.server.methods_called_debug

                if what_has_been_run:

                    expected = [Server.message_dispatcher.__name__]
                    actual = what_has_been_run

                    self.assertEqual(expected, actual)

                    break

                else:

                    self.fail("what_has_been_run is empty.")

        else:
            # timeout
            self.fail("message_dispatcher() timed-out.")

    def test_message_dispatcher_one_message_to_send(self) -> None:
        # all messages sent and received besides one, at the end of the list
        self.server.client_messages.waiting_messages = self.message_list

        self.server.client_messages.waiting_messages[-1]["broadcasted"][0]["message_sent_at"] = None
        self.server.client_messages.waiting_messages[-1]["broadcasted"][0]["message_received_at"] = None

        # here the client with randomised ip and port number is the sender while self.client_socket is the recipient
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            },
            {
                "client_name": self.client_message["broadcasted"][0]["client_name"],
                "client_address": (self.random_ip, self.random_port)
            }
        ]

        message_dispatcher_thread = threading.Thread(
            target=self.server.message_dispatcher,
            kwargs={
                "execute_once": True
            }
        )
        message_dispatcher_thread.start()

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if any messages were received
        while time() < end_time:

            expected = ServerResponseTypes.MESSAGE_FROM_CLIENT.value
            actual = self.client_socket.recv(RESPONSE_TYPE_HEADER_LENGTH).decode('utf-8')

            self.assertEqual(expected, actual)

        else:
            # timeout
            self.fail("message_dispatcher() timed-out.")

    def test_message_dispatcher_multiple_messages_to_send(self) -> None:
        # all messages sent and received besides few, at the end of the list
        self.server.client_messages.waiting_messages = self.message_list

        # set few messages as not sent and not received
        for i in range(3):
            self.server.client_messages.waiting_messages[-(i + 1)]["broadcasted"][0]["message_sent_at"] = None
            self.server.client_messages.waiting_messages[-(i + 1)]["broadcasted"][0]["message_received_at"] = None

        # here the client with randomised ip and port number is the sender while self.client_socket is the recipient
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            },
            {
                "client_name": self.client_message["broadcasted"][0]["client_name"],
                "client_address": (self.random_ip, self.random_port)
            }
        ]

        message_dispatcher_thread = threading.Thread(
            target=self.server.message_dispatcher,
            kwargs={
                "execute_once": True
            }
        )
        message_dispatcher_thread.start()

        end_time = time() + TIMEOUT_SECONDS

        # keep checking if any messages were received
        while time() < end_time:

            for i in range(3):

                expected = ServerResponseTypes.MESSAGE_FROM_CLIENT.value
                actual = self.client_socket.recv(RESPONSE_TYPE_HEADER_LENGTH).decode('utf-8')

                # empty the buffer
                msg_len = int(self.client_socket.recv(MESSAGE_LENGTH_HEADER_LENGTH).decode('utf-8'))
                _ = self.client_socket.recv(msg_len)

                self.assertEqual(expected, actual)

        else:
            # timeout
            self.fail("message_dispatcher() timed-out.")

    def test_log_text_file_path(self) -> None:
        log_filename = self.server.log_filename

        self.log_filenames += log_filename
        self.server.log(ServerEventTypes.STARTING, datetime.now())

        self.assertTrue(os.path.exists(self.log_file_path / log_filename))

    def test_log_filename(self) -> None:
        current_date = datetime.now()
        server_test = Server(__log_file_created_at=current_date)
        server_test.log(ServerEventTypes.STARTING, datetime.now())

        self.log_filenames += server_test.log_filename

        expected = "log_" + current_date.strftime("%Y%m%d%H%M%S%f") + ".txt"
        actual = server_test.log_filename

        self.assertEqual(expected, actual)
        self.assertTrue(os.path.exists(expected))

    def test_log_starting(self) -> None:
        self.server.log(ServerEventTypes.STARTING, self.log_current_date)

        expected = f"{self.log_current_date_str} [STARTING] Server is booting up..."

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_started(self) -> None:
        some_global_vars = {
            "CLIENT_LIMIT": 2,
            "PASSCODE": self.passcode
        }

        self.server.log(ServerEventTypes.STARTED, self.log_current_date, vars=some_global_vars)

        expected = f"{self.log_current_date_str} [STARTED] Server started. {[f'{k} = {v}' for k, v in some_global_vars]}"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_listening(self) -> None:
        self.server.log(ServerEventTypes.LISTENING, self.log_current_date, server_addr=self.server_addr)

        expected = f"{self.log_current_date_str} [LISTENING] Server is listening at on {self.server_addr[0]}:{self.server_addr[1]}"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_attempted_connection_accepted(self) -> None:
        self.server.log(
            ServerEventTypes.ATTEMPTED_CONNECTION,
            self.log_current_date,
            client_addr=self.client_addr,
            accepted=True
        )

        expected = f"{self.log_current_date_str} [ATTEMPTED_CONNECTION] Attempted connection from {self.client_addr[0]}:{self.client_addr[1]}."

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_attempted_connection_rejected(self) -> None:
        self.server.log(
            ServerEventTypes.ATTEMPTED_CONNECTION,
            self.log_current_date,
            client_addr=self.client_addr,
            accepted=False,
            reason="reached max number of clients (2)"
        )

        expected = f"{self.log_current_date_str} [ATTEMPTED_CONNECTION] Attempted connection from {self.client_addr[0]}:{self.client_addr[1]}. Rejected. Reason: 'reached max number of clients (2)'"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_new_client(self) -> None:
        self.server.log(ServerEventTypes.NEW_CLIENT, self.log_current_date, client_addr=self.client_addr, client_username=self.client_username)

        expected = f"{self.log_current_date_str} [NEW CLIENT] New client accepted {self.client_addr[0]}:{self.client_addr[1]} as '{self.client_username}'"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_active_clients(self) -> None:
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            },
            {
                "client_name": self.fake_client_username,
                "client_address": (self.random_ip, self.random_port)
            }
        ]

        self.server.log(ServerEventTypes.ACTIVE_CLIENTS, self.log_current_date, active_clients=self.server.approved_connections)

        expected = f"{self.log_current_date_str} [ACTIVE CLIENTS] Currently active clients: '{self.client_username}' {self.client_addr[0]}:{self.client_addr[1]}, '{self.fake_client_username}' {self.random_ip}:{self.random_port}"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_client_disconnected(self) -> None:
        self.server.approved_connections = [
            {
                "client_name": self.client_username,
                "client_address": self.client_addr
            }
        ]

        self.server.log(ServerEventTypes.CLIENT_DISCONNECTED, self.log_current_date, client_username=self.client_username, client_addr=self.client_addr)

        expected = f"{self.log_current_date_str} [CLIENT DISCONNECTED] Client '{self.client_username}' {self.client_addr[0]}:{self.client_addr[1]} disconnected."

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_message_received(self) -> None:
        message = {
            "client_name": "foo",
            "timestamps": {
                "client_sent": datetime.now(),
                "server_received": datetime.now(),
            },
            "message": "bar",
            "broadcasted": [
                {
                    "client_name": "bar",
                    "client_connected": True
                }
            ],
            "message_id": "123"
        }

        self.server.log(ServerEventTypes.MESSAGE_RECEIVED, self.log_current_date, message=message)

        expected = f"{self.log_current_date_str} [MESSAGE RECEIVED] Received message message_id='123', client_name=" \
                   f"'foo', timestamps.client_sent={message['timestamps']['client_sent']}, timestamps.server_" \
                   f"received={message['timestamps']['server_received']}, message='bar', broadcasted.0.client_name=" \
                   f"'bar', broadcasted.0.client_connected=True"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_message_dispatched(self) -> None:
        self.server.log(ServerEventTypes.MESSAGE_DISPATCHED, self.log_current_date, message_id='123', timstamp=self.log_current_date)

        expected = f"{self.log_current_date_str} [MESSAGE DISPATCHED] Dispatched message '123' at {self.log_current_date.strftime('%Y-%m-%d %H:%M:%S.%f')}."

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_messaged_delivered(self) -> None:
        self.server.log(ServerEventTypes.MESSAGED_DELIVERED, self.log_current_date, message_id='123', timstamp=self.log_current_date)

        expected = f"{self.log_current_date_str} [MESSAGED DELIVERED] Delivered message '123' at {self.log_current_date.strftime('%Y-%m-%d %H:%M:%S.%f')}"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_missing_message(self) -> None:
        self.server.log(ServerEventTypes.MISSING_MESSAGE, self.log_current_date, message_id='123', client_add=self.client_addr, client_username=self.client_username)

        expected = f"{self.log_current_date_str} [MISSING MESSAGE] Found message '123' sent but not delivered to '{self.client_username}' {self.client_addr[0]}:{self.client_addr[1]}"

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_log_shutting_down(self) -> None:
        self.server.log(ServerEventTypes.SHUTTING_DOWN, self.log_current_date)

        expected = f"{self.log_current_date_str} [SHUTTING DOWN] Server is shutting down..."

        with open(self.log_file_path / self.sample_log_filename, 'r') as f:
            lines = f.readlines()

        actual = lines[0]

        self.assertEqual(1, len(lines))
        self.assertEqual(expected, actual)

    def test_handle_missing_message(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
