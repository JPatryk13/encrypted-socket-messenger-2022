import json
import operator
import pickle
import random
import unittest
from datetime import datetime
from src.message_handler import MessageHandler
import socket
import threading
from typing import Optional, Union, Tuple
from dotenv import load_dotenv
from pathlib import Path
import os
from pydantic import BaseModel, Extra, validator, ValidationError
from enum import Enum
from src.schema import MessageSchema
from collections import OrderedDict


class SampleSubSchema(BaseModel):
    field_a: str
    field_b: str


class SampleEnumClass(str, Enum):
    f0 = 'not_given'
    f1 = 'f1'
    f2 = 'f2'
    f3 = 'f3'


class SampleSchema(BaseModel):
    field1: str
    field2: int
    field3: Optional[float] = None
    field4: Union[int, str, None] = None  # match and convert to the first possible type
    field5: str | int | None = None  # match and convert to the first possible type
    field6: Optional[Tuple[str, int]] = None
    field7: Optional[Tuple[str, int]] = None
    field8: Optional[SampleSubSchema] = None
    field9: Optional[SampleEnumClass] = None

    class Config:
        use_enum_values = True
        extra = Extra.forbid

    @validator('field6', 'field7')
    def validate_tuple(cls, v):
        if v[0].count('.') == 3 and v[1] > 4000:
            return v
        else:
            raise ValidationError("Oops! Something went wrong.")


class TestMessageHandler(unittest.TestCase):
    def setUp(self) -> None:
        # use local address for the connection
        self.ADDR = (socket.gethostbyname(socket.gethostname()), 5050)

        # the SampleSchema is used for some tests of append_message function
        self.sender = MessageHandler(SampleSchema)

        # other functions' tests (+ extra append_message() test) will use MessageSchema from schema.py
        self.sender2 = MessageHandler(MessageSchema)
        # example message
        self.message = {
            "header": len(bytes("Hello world!", encoding='utf-8')),
            "message_id": "20221101222010000294127000000001",
            "client_name": "John",
            "timestamps": {
                "client_sent": datetime(2022, 11, 1, 22, 20, 10, 294),
                "server_received": datetime(2022, 11, 1, 22, 20, 11, 1261),
            },
            "message": "Hello world!",
            "client_address": ("127.0.0.1", 5050),
            "broadcasted": [
                {
                    "client_name": "Mike",
                    "client_connected": False,
                    "message_sent_at": None,
                    "message_received_at": None
                }
            ]
        }

        # list of example messages with some modifications for each one
        self.client_list = ["John", "Mike"]

        self.message_list = [
            {
                "header": len(bytes("Hello world!", encoding='utf-8')),
                "message_id": f"202211012220{str(i).zfill(2)}000029412700000000{i % 2}",
                "client_name": self.client_list[i % 2],
                "timestamps": {
                    "client_sent": datetime(2022, 11, 1, 22, 20, i, 294),
                    "server_received": datetime(2022, 11, 1, 22, 20, i + 1, 1261),
                },
                "message": "Hello world!",
                "client_address": (f"127.0.0.{i % 2}", 5050),
                "broadcasted": [
                    {
                        "client_name": self.client_list[i % 2],
                        "client_connected": False,
                        "message_sent_at": None,
                        "message_received_at": None
                    }
                ]
            } for i in range(10)
        ]
        self.sender2.waiting_messages = self.message_list

        # Set up a server
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.ADDR)
        self.server.listen()

        # set up a client
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(self.ADDR)

        # load environmental variables
        dotenv_path = Path(__file__).parent.parent.resolve() / ".env"
        load_dotenv(dotenv_path=dotenv_path)
        self.FORMAT = os.getenv('FORMAT')
        self.HEADER_LENGTH = int(os.getenv('HEADER_LENGTH'))

    def tearDown(self) -> None:
        self.server.close()
        self.client.close()

    def test_append_message_all_fields_str_where_union(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field3": 7.13,
            "field4": "bar",
            "field5": "bar",
            "field6": ("127.0.0.1", 5050),
            "field7": ("127.0.0.1", 5050),
            "field8": {
                "field_a": "foo",
                "field_b": "bar"
            },
            "field9": SampleEnumClass.f0.value
        }
        self.sender.append_message(**msg)

        expected = [msg]
        actual = self.sender.waiting_messages
        self.assertEqual(expected, actual)

    def test_append_message_all_fields_int_where_union(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field3": 7.13,
            "field4": 1,
            "field5": 2,
            "field6": ("127.0.0.1", 5050),
            "field7": ("127.0.0.1", 5050),
            "field8": {
                "field_a": "foo",
                "field_b": "bar"
            },
            "field9": SampleEnumClass.f0.value
        }
        self.sender.append_message(**msg)

        expected = [msg]
        expected[0]["field5"] = str(expected[0]["field5"])
        actual = self.sender.waiting_messages
        self.assertEqual(expected, actual)

    def test_append_message_only_required_fields(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713
        }
        self.sender.append_message(**msg)

        expected = [
            dict(msg, **{key: None for key in ["field3", "field4", "field5", "field6", "field7", "field8", "field9"]})
        ]
        actual = self.sender.waiting_messages
        self.assertEqual(expected, actual)

    def test_append_message_wrong_datatype(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field3": "bar"
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_undefined_field(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "undefined_field": "bar"}
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_one_tuple_incorrect_datatype(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field6": (5050, "127.0.0.1"),
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_both_tuples_incorrect_datatype(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field6": (5050, "127.0.0.1"),
            "field7": (5050, "127.0.0.1"),
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_tuple_too_many_elements(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field6": ("127.0.0.1", 5050, b'xyz'),
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_tuple_incorrect_ipv4(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field6": ("127.0.0", 5050),
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_tuple_incorrect_port_number(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field6": ("127.0.0.1", 50),
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    def test_append_message_enum_field_wrong_value(self) -> None:
        msg = {
            "field1": "foo",
            "field2": 713,
            "field9": 'incorrect'
        }
        with self.assertRaises(ValidationError):
            self.sender.append_message(**msg)

        actual = self.sender.waiting_messages
        self.assertEqual([], actual)

    @unittest.skip("message_handler.py no longer hosts message_dispatcher, test left as a reference.")
    def test_message_dispatcher(self) -> None:
        expected = {
            "field1": "foo",
            "field2": 713
        }
        self.sender.waiting_messages.append(expected)

        conn, _ = self.server.accept()  # wait to accept any incoming messages

        print(type(self.client))

        # handle sending the message in a separate thread
        client_thread = threading.Thread(target=self.sender.message_dispatcher, args=[self.client])
        client_thread.start()

        print("started threading")

        msg_length = int(conn.recv(self.HEADER_LENGTH).decode(self.FORMAT))

        print(msg_length)

        actual = pickle.loads(conn.recv(msg_length))

        conn.send(str(True).encode(self.FORMAT))

        print(actual)

        conn.close()

        self.assertEqual(expected, actual)

    @unittest.skip("message_handler.py no longer hosts message_dispatcher, test left as a reference.")
    def test_message_dispatcher_pop_message(self) -> None:
        self.sender.waiting_messages.append({"msg": "Hello World!", "client_name": 'John'})

        conn, _ = self.server.accept()  # wait to accept any incoming messages

        # handle sending the message in a separate thread
        client_thread = threading.Thread(target=self.sender.message_dispatcher, args=[conn])
        client_thread.start()

        if not client_thread.is_alive():
            self.assertEqual([], self.sender.waiting_messages)

    def test_append_message_message_schema(self) -> None:
        self.sender2.waiting_messages = []
        self.sender2.append_message(**self.message)

        expected = [self.message]
        actual = self.sender2.waiting_messages

        self.assertEqual(expected, actual)

    def test_append_message_timestamp_key(self) -> None:
        self.sender2.append_message(**self.message)

        expected = ["timestamps", "client_sent"]
        actual = self.sender2.timestamp_key

        self.assertEqual(expected, actual)

    def test_append_message_sorting_by_date(self) -> None:
        expected = [msg["timestamps"]["client_sent"] for msg in self.message_list]

        self.sender2.waiting_messages = []
        input_list = random.sample(self.message_list, len(self.message_list))
        for msg in input_list:
            self.sender2.append_message(**msg)

        actual = [msg["timestamps"]["client_sent"] for msg in self.sender2.waiting_messages]

        self.assertEqual(expected, actual)

    def test_append_message_message_schema_no_id(self) -> None:
        self.sender2.waiting_messages = []

        expected = self.message["message_id"]

        self.message["message_id"] = None
        self.sender2.append_message(**self.message)

        actual = self.sender2.waiting_messages[0]["message_id"]

        self.assertEqual(expected, actual)

    def test_get_schema_schema_as_dict(self) -> None:
        self.sender2.waiting_messages = []

        actual = self.sender2.get_schema(schema_as='dict')
        self.assertIsInstance(actual, dict)
        self.assertTrue("properties" in actual.keys())

    def test_get_schema_schema_as_json(self) -> None:
        self.sender2.waiting_messages = []

        actual = self.sender2.get_schema(schema_as='json')
        self.assertIsInstance(actual, str)
        try:
            json.loads(actual)
        except ValueError:
            self.fail("self.sender2.get_schema(schema_as='json') does not return a valid json-like string.")

    def test_get_schema_schema_as_wrong_input(self) -> None:
        self.sender2.waiting_messages = []

        with self.assertRaises(Exception) as err:
            expected = "The parameter 'schema_as' can only take values 'json', 'dict'. wrong_input was given."
            actual = self.sender2.get_schema(schema_as='wrong_input')

            self.assertEqual(expected, actual)
            self.assertEqual(None, actual)

    def test_get_schema_get_only_correct_input(self) -> None:
        self.sender2.waiting_messages = []

        try:
            actual = self.sender2.get_schema(get_only="description")
        except KeyError as err:
            self.fail(err)
        else:
            self.assertIsInstance(actual, str)

    def test_get_schema_get_only_wrong_input(self) -> None:
        self.sender2.waiting_messages = []

        key_list = json.loads(MessageSchema.schema_json())["properties"].keys()
        expected_err_msg = f"Schema is not compatible with the request. Could not find field wrong_input in {key_list}."
        with self.assertRaises(KeyError) as context:
            self.sender2.get_schema(get_only="wrong_input")
            self.assertTrue(expected_err_msg in str(context.exception))

    def test_get_not_broadcasted_messages_no_messages(self) -> None:
        actual = self.sender2.get_not_broadcasted_messages(recipient_name="John")
        self.assertEqual([], actual)

    def test_get_not_broadcasted_messages_no_recipients(self) -> None:
        self.message.update(broadcasted=[])
        self.sender2.waiting_messages.append(self.message)

        actual = self.sender2.get_not_broadcasted_messages(recipient_name="John")

        self.assertEqual([], actual)

    def test_get_not_broadcasted_messages_user_disconnected(self) -> None:
        self.message["broadcasted"][0].update(user_connected=False)
        self.sender2.waiting_messages.append(self.message)

        actual = self.sender2.get_not_broadcasted_messages(recipient_name="John")

        self.assertEqual([], actual)

    def test_get_not_broadcasted_messages_single_message_found(self) -> None:
        self.message_list[4]["broadcasted"][0] = {
            "client_name": "David",
            "client_connected": True,
            "message_sent_at": None,
            "message_received_at": None
        }
        self.sender2.waiting_messages = self.message_list

        actual = len(self.sender2.get_not_broadcasted_messages(recipient_name="David"))
        expected = 1

        self.assertEqual(expected, actual)

    def test_get_not_broadcasted_messages_multiple_messages_found(self) -> None:
        for i, _ in enumerate(self.message_list):
            self.message_list[i]["broadcasted"][0].update(client_connected=True)
        self.sender2.waiting_messages = self.message_list

        actual = len(self.sender2.get_not_broadcasted_messages(recipient_name="John"))
        expected = 5

        self.assertEqual(expected, actual)

    def test_get_messages_no_messages(self) -> None:
        self.sender2.waiting_messages = []

        expected = []
        _, actual = self.sender2.get_messages(client_name="John")
        self.assertEqual(expected, actual)

    def test_get_messages_by_message_id_conditions_kwargs(self) -> None:
        self.sender2.waiting_messages = self.message_list
        expected = [self.message_list[0]]
        _, actual = self.sender2.get_messages(message_id=self.message_list[0]["message_id"])
        self.assertEqual(expected, actual)

    def test_get_messages_all_messages(self) -> None:
        self.sender2.waiting_messages = self.message_list
        expected = self.message_list
        _, actual = self.sender2.get_messages()
        self.assertEqual(expected, actual)

    def test_get_messages_by_timestamp(self) -> None:
        self.sender2.waiting_messages = self.message_list
        expected = [self.message_list[2]]
        _, actual = self.sender2.get_messages(at="timestamps", client_sent=self.message_list[2]["timestamps"]["client_sent"])
        self.assertEqual(expected, actual)

    def test_get_messages_by_receiving_client_name(self) -> None:
        self.sender2.waiting_messages = self.message_list
        expected = [msg for msg in self.message_list if msg["broadcasted"][0]["client_name"] == self.message_list[2]["broadcasted"][0]["client_name"]]
        _, actual = self.sender2.get_messages(
            at="broadcasted",
            client_name=self.message_list[2]["broadcasted"][0]["client_name"]
        )
        self.assertEqual(expected, actual)

    def test_get_messages_err_condition_key_name(self) -> None:
        self.assertRaises(KeyError, self.sender2.get_messages, foo="bar")

    def test_get_messages_err_condition_value_type(self) -> None:
        self.assertRaises(ValueError, self.sender2.get_messages, client_name=2)

    def test_get_messages_err_at_key_name(self) -> None:
        self.assertRaises(KeyError, self.sender2.get_messages, at="foo", client_name="bar")

    def test_update_messages_no_message(self) -> None:
        self.sender2.waiting_messages = []

        expected = []
        self.sender2.update_messages(field_name="client_connected", value=True, at="broadcasted", client_name="Mike")
        actual = self.sender2.waiting_messages
        self.assertEqual(expected, actual)

    @unittest.skip("The function passes the test. Requires 'message' field to be 'MODIFIABLE' in schema.")
    def test_update_messages_non_embedded_field(self) -> None:
        self.sender2.waiting_messages = self.message_list
        self.sender2.update_messages("message", "foo", message_id=self.message_list[0]["message_id"])

        expected = "foo"
        actual = self.sender2.waiting_messages[0]["message"]

        self.assertEqual(expected, actual)

    def test_update_messages_embedded_field(self) -> None:
        self.sender2.waiting_messages = self.message_list
        self.sender2.update_messages(field_name="client_connected", value=True, at="broadcasted", client_name=self.message_list[0]["broadcasted"][0]["client_name"])

        actual = self.sender2.waiting_messages[0]["broadcasted"][0]["client_connected"]

        self.assertTrue(actual)

    def test_update_messages_err_field_not_modifiable(self) -> None:
        self.assertRaises(Exception, self.sender2.update_messages, field_name="message_id", value="foo")

    def test_update_messages_err_wrong_value_type(self) -> None:
        self.assertRaises(ValueError, self.sender2.update_messages, field_name="client_connected", value="True", at="broadcasted")

    def test_query_get_messages_no_messages(self) -> None:
        self.sender2.waiting_messages = []

        expected = []
        actual = self.sender2.query("GET ALL")
        self.assertEqual(expected, actual)

    def test_query_get_messages_by_message_id(self) -> None:
        self.sender2.waiting_messages = self.message_list

        expected = [self.message_list[0]]
        actual = self.sender2.query("GET WHERE message_id=={}", where_val=[self.message_list[0]["message_id"]])

        self.assertEqual(expected, actual)

    def test_query_get_messages_all_messages(self) -> None:
        self.sender2.waiting_messages = self.message_list

        expected = self.message_list
        actual = self.sender2.query("GET ALL")

        self.assertEqual(expected, actual)

    def test_query_get_messages_by_timestamp(self) -> None:
        self.sender2.waiting_messages = self.message_list

        expected = [self.message_list[2]]
        actual = self.sender2.query("GET WHERE timestamps.client_sent=={}", where_val=[self.message_list[2]["timestamps"]["client_sent"]])
        self.assertEqual(expected, actual)

    def test_query_get_messages_by_receiving_client_name(self) -> None:
        self.sender2.waiting_messages = self.message_list

        expected = [msg for msg in self.message_list if
                    msg["broadcasted"][0]["client_name"] == self.message_list[2]["broadcasted"][0]["client_name"]]

        actual = self.sender2.query(
            "GET WHERE broadcasted.client_name=={}",
            where_val=[self.message_list[2]["broadcasted"][0]["client_name"]]
        )

        self.assertEqual(expected, actual)

    def test_query_get_messages_err_condition_key_name(self) -> None:
        self.assertRaises(KeyError, self.sender2.query, _query="GET WHERE foo=={}", where_val=["bar"])

    def test_query_get_messages_err_condition_value_type(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="GET WHERE client_name=={}", where_val=[2])

    def test_query_get_messages_err_at_key_name(self) -> None:
        self.assertRaises(KeyError, self.sender2.query, _query="GET WHERE foo.client_name=={}", where_val=["bar"])

    def test_query_update_messages_no_message(self) -> None:
        self.sender2.waiting_messages = []

        self.sender2.query("UPDATE broadcasted.client_connected={} WHERE client_name=={}", update_val=[True], where_val=["Mike"])

        expected = []
        actual = self.sender2.waiting_messages

        self.assertEqual(expected, actual)

    def test_query_update_messages_embedded_field(self) -> None:
        self.sender2.waiting_messages = self.message_list

        self.sender2.query("UPDATE broadcasted.client_connected={} WHERE broadcasted.client_name=={}", update_val=[True], where_val=[self.message_list[0]["broadcasted"][0]["client_name"]])

        actual = self.sender2.waiting_messages[0]["broadcasted"][0]["client_connected"]

        self.assertTrue(actual)

    def test_query_update_messages_err_field_not_modifiable(self) -> None:
        self.assertRaises(Exception, self.sender2.query, _query="UPDATE ALL message_id={}", update_val=["foo"])

    def test_query_update_messages_err_wrong_value_type(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="UPDATE ALL broadcasted.client_connected={}", update_val=["str"])

    def test_query_get_messages_by_date_greater_than(self) -> None:

        expected = [msg for msg in self.sender2.waiting_messages
                    if msg["timestamps"]["client_sent"] >= datetime(2022, 11, 1, 22, 20, 4)]

        actual = self.sender2.query("GET WHERE timestamps.client_sent>={}", where_val=[datetime(2022, 11, 1, 22, 20, 4)])

        self.assertEqual(expected, actual)

    def test_query_get_messages_by_two_embedded_fields(self) -> None:

        expected = [msg for msg in self.sender2.waiting_messages if
                    msg["timestamps"]["client_sent"] >= datetime(2022, 11, 1, 22, 20, 3)
                    and msg["broadcasted"][0]["client_name"] == "John"]

        actual = self.sender2.query("GET WHERE timestamps.client_sent>={}, broadcasted.client_name=={}", where_val=[datetime(2022, 11, 1, 22, 20, 3), "John"])

        self.assertEqual(expected, actual)

    def test_query_get_messages_by_client_address_and_embedded_field(self) -> None:

        expected = [msg for msg in self.message_list
                    if msg["client_address"] == (f"127.0.0.1", 5050)
                    and msg["timestamps"]["client_sent"] >= datetime(2022, 11, 1, 22, 20, 4)]

        actual = self.sender2.query("GET WHERE client_address=={}, timestamps.client_sent>={}", where_val=[(f"127.0.0.1", 5050), datetime(2022, 11, 1, 22, 20, 4)])

        self.assertEqual(expected, actual)

    def test_query_get_messages_explicit_and(self) -> None:

        expected = [msg for msg in self.message_list
                    if msg["client_address"] == (f"127.0.0.1", 5050)
                    and msg["timestamps"]["client_sent"] >= datetime(2022, 11, 1, 22, 20, 4)]

        actual = self.sender2.query("GET WHERE client_address=={} AND timestamps.client_sent>={}", where_val=[(f"127.0.0.1", 5050), datetime(2022, 11, 1, 22, 20, 4)])

        self.assertEqual(expected, actual)

    @unittest.skip("OR operator currently not supported")
    def test_query_get_messages_explicit_or(self) -> None:
        expected = [msg for msg in self.message_list
                    if msg["client_address"] == (f"127.0.0.1", 5050)
                    or msg["timestamps"]["client_sent"] >= datetime(2022, 11, 1, 22, 20, 4)]

        actual = self.sender2.query("GET WHERE client_address=={} OR timestamps.client_sent>={}", where_val=[(f"127.0.0.1", 5050), datetime(2022, 11, 1, 22, 20, 4)])

        self.assertEqual(expected, actual)

    def test_query_delete_where_message_id(self) -> None:
        expected = self.sender2.waiting_messages[1:]

        self.sender2.query("DELETE WHERE message_id=={}", where_val=[self.sender2.waiting_messages[0]["message_id"]])

        actual = self.sender2.waiting_messages

        self.assertEqual(expected, actual)

    def test_query_delete_where_broadcasted_client_name(self) -> None:
        self.sender2.query("DELETE WHERE broadcasted.client_name=={}", where_val=["John"])

        expected = [msg for msg in self.message_list if msg["broadcasted"][0]["client_name"] != "John"]
        actual = self.sender2.waiting_messages

        self.assertEqual(expected, actual)

    def test_query_delete_in_broadcasted_where_client_connected(self) -> None:

        # set client_connected=True
        self.sender2.waiting_messages[0]["broadcasted"][0]["client_connected"] = True

        # remove the client from broadcasted list
        self.sender2.query("DELETE IN(broadcasted) WHERE broadcasted.client_connected=={}", where_val=[True])

        expected = []
        actual = self.sender2.waiting_messages[0]["broadcasted"]

        self.assertEqual(expected, actual)

    def test_query_delete_all(self) -> None:
        self.sender2.query("DELETE ALL")
        expected = []
        actual = self.sender2.waiting_messages
        self.assertEqual(expected, actual)

    def test_query_delete_where_timestamps_client_sent_older_than(self) -> None:
        self.sender2.query("DELETE WHERE timestamps.server_received<={}", where_val=[datetime(2022, 11, 1, 22, 20, 5)])

        expected = [msg for msg in self.message_list if operator.gt(msg["timestamps"]["server_received"], datetime(2022, 11, 1, 22, 20, 5))]
        actual = self.sender2.waiting_messages

        print(len(expected), len(actual))

        self.assertEqual(expected, actual)

    def test_query_not_allowed_characters_numbers(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="GET WHERE var0=={}", where_val=["str"])

    def test_query_not_allowed_characters_punctuation(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="GET WHERE var:s=={}", where_val=["str"])

    def test_query_not_allowed_characters_symbols(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="GET WHERE var&s=={}", where_val=["str"])

    def test_query_not_allowed_method(self) -> None:
        self.assertRaises(ValueError, self.sender2.query, _query="PRINT ALL")

    def test_query_err_semicolons1(self) -> None:
        self.assertRaises(
            ValueError,
            self.sender2.query,
            _query="GET WHERE client_name=={} , broadcasted.client_name=={}", where_val=["John", "Mike"]
        )

    def test_query_err_semicolons2(self) -> None:
        self.assertRaises(
            ValueError,
            self.sender2.query,
            _query="GET WHERE client_name=={},broadcasted.client_name=={}", where_val=["John", "Mike"]
        )

    def test_query_improper_query(self) -> None:
        self.assertRaises(Exception, self.sender2.query, _query="WHERE DELETE message_id=={}", args=["bar"])


if __name__ == "__main__":
    unittest.main()
