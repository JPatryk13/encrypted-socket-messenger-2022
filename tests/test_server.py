import unittest
from pathlib import Path
from src.server import Server
import os
from datetime import datetime
import psutil
import socket
import pprint as pp


class TestServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = Server()
        self.passcode = self.server.get_passcode()

    def test_handle_clients_new_connection_correct_passcode_clients_list(self) -> None:
        expected = [("127.0.0.1", 5050)]
        self.server.handle_clients(client_response_code='p', user_message=self.passcode, addr=("127.0.0.1", 5050))
        actual = self.server.approved_connections
        self.assertEqual(expected, actual)

    def test_handle_clients_new_connection_correct_passcode_messages_list(self) -> None:
        expected = [
            {
                "header": None,
                "timestamps": {
                    "message_created": None,
                    "server_sent": None,
                    "client_received": None
                },
                "message": None,
                "client_address": None,
            }
        ]
        self.server.handle_clients(client_response_code='p', user_message=self.passcode, addr=("127.0.0.1", 5050))
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
