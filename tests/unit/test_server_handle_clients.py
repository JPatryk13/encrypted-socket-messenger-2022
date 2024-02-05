import pickle
import unittest
import socket

from src.server import Server
from src.shared_enum_vars import ClientResponseTypes, ServerResponseTypes


class TestServerHandleClients(unittest.TestCase):
    def setUp(self) -> None:
        # Spin up the server
        self.server = Server()
        self.server_addr = self.server.get_addr()

        # Get the correct passcode and generate a wrong one
        self.correct_passcode = self.server.get_passcode()
        self.wrong_passcode = self.server.get_passcode()[3:]  # remove first few bytes/characters

        local_ip = socket.gethostbyname(socket.gethostname())

        # Instantiate first client socket and connect to the server
        self.client_socket_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket_1.bind((local_ip, 0))
        self.client_socket_1.connect(self.server_addr)

        # Get details about the first client
        self.client_addr_1 = self.client_socket_1.getsockname()
        self.client_username_1 = "client1"

        self.client_socket_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket_2.bind((local_ip, 0))
        self.client_socket_2.connect(self.server_addr)

        self.client_addr_2 = self.client_socket_2.getsockname()
        self.client_username_2 = "client2"

    def __test_handle_clients_server_messages_list(
            self,
            server_resp_type: ServerResponseTypes,
            *, client_name: bool = True,
            info: str | None = None
    ):
        """
        Conducts part of the test responsible for checking if the message exists and has an appropriate structure in the
        server.server_messages. It requires to execute handle_clients function separately. Works only for a single
        client as the recipient - self.client_socket_1
        """

        expected = {
            "response_type": server_resp_type,
            "broadcasted": [
                {
                    "client_name": self.client_username_1 if client_name else pickle.dumps(self.client_addr_1),
                    "message_sent_at": None,
                    "message_received_at": None
                }
            ],
            "server_addr": self.server.get_addr(),
            "info": info
        }

        no_of_server_waiting_messages = len(self.server.server_messages.waiting_messages)

        print(self.server.server_messages.waiting_messages)

        self.assertEqual(1, no_of_server_waiting_messages)

        actual = self.server.server_messages.waiting_messages[0]

        self.assertIn("message_id", actual.keys())
        self.assertIn("created_at", actual.keys())

        del actual["message_id"]
        del actual["created_at"]

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_sockets_list(self) -> None:
        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.correct_passcode
        )

        expected = [self.client_socket_1]
        actual = self.server.sockets_list[1:]

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_server_messages_list(self) -> None:

        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.correct_passcode
        )

        self.__test_handle_clients_server_messages_list(ServerResponseTypes.PASSCODE_CORRECT, client_name=False)

    def test_handle_clients_new_connection_incorrect_passcode_clients_list(self) -> None:
        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode
        )

        expected = []
        actual = self.server.sockets_list[1:]

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_messages_list(self) -> None:
        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.PASSCODE_GIVEN,
            client_message=self.wrong_passcode
        )

        self.__test_handle_clients_server_messages_list(ServerResponseTypes.PASSCODE_INCORRECT, client_name=False)

    def test_handle_clients_client_disconnected_after_username_sockets_and_clients_lists(self) -> None:
        self.server.sockets_list.append(self.client_socket_1)
        self.server.clients_list = [
            {
                "client_name": self.client_username_1,
                "addr": self.client_addr_1
            }
        ]

        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        expected = []
        actual_sockets = self.server.sockets_list[1:]
        actual_clients = self.server.clients_list

        self.assertEqual(expected, actual_sockets)
        self.assertEqual(expected, actual_clients)

    def test_handle_clients_client_disconnected_after_passcode_sockets_and_clients_lists(self) -> None:
        self.server.sockets_list.append(self.client_socket_1)

        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        expected = []
        actual = self.server.sockets_list[1:]

        self.assertEqual(expected, actual)

    def test_handle_clients_username_correct_messages_list(self) -> None:
        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.USERNAME_GIVEN,
            client_message=self.client_username_1
        )
        self.__test_handle_clients_server_messages_list(ServerResponseTypes.USERNAME_ACCEPTED)

    def test_handle_clients_second_client_joined_messages_list(self) -> None:
        self.server.sockets_list += [self.client_socket_1, self.client_socket_2]
        self.server.clients_list = [{"client_name": self.client_username_1, "addr": self.client_addr_1}]

        self.server.handle_clients(
            client_socket=self.client_socket_2,
            client_response_code=ClientResponseTypes.USERNAME_GIVEN,
            client_message=self.client_username_2
        )

        expected = {
            "response_type": ServerResponseTypes.CLIENT_CONNECTED,
            "broadcasted": [
                {
                    "client_name": self.client_username_1,
                    "message_sent_at": None,
                    "message_received_at": None
                }
            ],
            "server_addr": self.server.get_addr(),
            "info": ''.join([x.zfill(3) for x in self.client_addr_2[0].split('.')]) + str(self.client_addr_2[1]).zfill(6) + self.client_username_2
        }

        actual = self.server.server_messages.waiting_messages

        for msg in actual:
            del msg["message_id"]
            del msg["created_at"]

        self.assertIn(expected, actual)

    def test_handle_clients_username_already_exists_messages_list(self) -> None:
        self.server.sockets_list += [self.client_socket_1, self.client_socket_2]
        self.server.clients_list = [{"client_name": self.client_username_2, "addr": self.client_addr_2}]

        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.USERNAME_GIVEN,
            client_message=self.client_username_2
        )

        self.__test_handle_clients_server_messages_list(
            server_resp_type=ServerResponseTypes.USERNAME_ALREADY_EXISTS,
            client_name=False
        )

    def test_handle_clients_second_client_left(self) -> None:
        self.server.sockets_list += [self.client_socket_1, self.client_socket_2]
        self.server.clients_list = [
            {"client_name": self.client_username_1, "addr": self.client_addr_1},
            {"client_name": self.client_username_2, "addr": self.client_addr_2}
        ]

        self.server.handle_clients(
            client_socket=self.client_socket_2,
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        actual_sockets_list = self.server.sockets_list[1:]
        actual_clients_list = self.server.clients_list

        expected_sockets_list = [self.client_socket_1]
        expected_clients_list = [{"client_name": self.client_username_1, "addr": self.client_addr_1}]

        self.assertEqual(expected_sockets_list, actual_sockets_list)
        self.assertEqual(expected_clients_list, actual_clients_list)

        self.__test_handle_clients_server_messages_list(
            server_resp_type=ServerResponseTypes.CLIENT_DISCONNECTED,
            info=''.join([x.zfill(3) for x in self.client_addr_2[0].split('.')]) + str(self.client_addr_2[1]).zfill(6)
        )

    def test_handle_clients_client_disconnected_before_passcode(self) -> None:
        self.server.handle_clients(
            client_socket=self.client_socket_1,
            client_response_code=ClientResponseTypes.CLIENT_DISCONNECTED,
            client_message=None
        )

        actual_sockets_list = self.server.sockets_list[1:]
        actual_clients_list = self.server.clients_list

        self.assertEqual([], actual_sockets_list)
        self.assertEqual([], actual_clients_list)


if __name__ == "__main__":
    unittest.main()
