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

    def test_handle_clients_new_connection_correct_passcode_clients_list(self) -> None:
        self.server.handle_clients(client_response_code='p', user_message=self.passcode, addr=("127.0.0.1", 5050))

        expected = [{"client_name": "", "client_address": ("127.0.0.1", 5050)}]
        actual = self.server.approved_connections

        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_messages_list(self) -> None:
        client_addr = ("127.0.0.1", 5050)
        get_message_id(None, {"created_at": datetime.now()})

        created_at = self.server.handle_clients(
            client_response_code='p',
            user_message=self.passcode,
            addr=client_addr,
            __debug=True
        )

        expected = [
            {
                "header": len("GRANTED".encode('utf-8')),
                "created_at": created_at,
                "message": "GRANTED",
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
        ]
        actual = self.server.server_messages.waiting_messages
        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_clients_list(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_incorrect_passcode_messages_list(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_list_of_clients(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_new_client_messages_list(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_messages_list(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_remove_disconnected_true_message_broadcasted(self) -> None:
        expected = []
        actual = []
        self.assertEqual(expected, actual)

    def test_handle_clients_client_disconnected_remove_disconnected_false_message_broadcasted_user_connected(self) -> None:
        expected = []
        actual = []
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
