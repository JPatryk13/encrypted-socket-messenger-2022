from typing import Optional, Type, Any, get_origin, get_args
import json
from datetime import datetime, time, date
import os
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, ValidationError
from pydantic.utils import lenient_issubclass, lenient_isinstance
from .schema import MessageSchema
import re
from collections.abc import Callable
import operator


class MessageHandler:
    def __init__(self, message_schema: Type[BaseModel], sort_messages_by_date: bool = False):
        # The list will store all messages
        self.waiting_messages = []

        # key to the field by which messages will be sorted, will be initialized as soon as the first message will be
        # added to the list
        self.sort_messages_by_date = sort_messages_by_date
        self.timestamp_key = None

        # The schema class can be referenced throughout the class using self.Schema
        self.Schema = message_schema

        # define the error message for any time user tries to access non-existing field in the schema
        def f(field_name: str, key_list: list[str] = json.loads(self.Schema.schema_json())):
            return f"Schema is not compatible with the request. Could not find field {field_name} in {key_list}."

        self.key_err_msg = f

        # Initialize environmental variables
        dotenv_path = Path(__file__).parent.parent.resolve() / ".env"
        load_dotenv(dotenv_path=dotenv_path)
        self.FORMAT = os.getenv('FORMAT')
        self.HEADER_LENGTH = int(os.getenv('HEADER_LENGTH'))

    def get_schema(self, *, schema_as: str = 'dict', get_only: str | None = None) -> Any:
        schema_json = self.Schema.schema_json(indent=3)
        schema_dict = json.loads(schema_json)
        # if get_only specified try to access the key in the schema
        if get_only:
            try:
                return schema_dict[get_only]
            except KeyError:
                raise KeyError(self.key_err_msg(get_only))
        # return the schema if get_only not specified
        else:
            if schema_as == 'json':
                return schema_json
            elif schema_as == 'dict':
                return schema_dict
            else:
                raise Exception(f"The parameter 'schema_as' can only take values 'json', 'dict'. {schema_as} was given.")

    def append_message(self, **kwargs) -> None:
        try:

            # get dictionary that was given via **kwargs if it matches the schema
            message = self.Schema(**kwargs).dict()

        except ValidationError as err:

            raise err

        else:

            # append the message to the list of waiting messages
            self.waiting_messages.append(message)

            if self.sort_messages_by_date:
                # initialize timestamp_key if there is none
                if self.timestamp_key is None:
                    # the [0] at the end = we want only the first list of keys (multiple are being returned)
                    self.timestamp_key = SortByDate.find_datetime_value_key(self.waiting_messages[0])[0]

                # sort messages by date
                self.waiting_messages = SortByDate.sort_by_date(self.waiting_messages, *self.timestamp_key)

    def __is_in_schema(
            self,
            *, fields: list[str],
            schema_class: Type[BaseModel],
            check_if_modifiable: bool,
            value: Any = None
    ) -> None:
        """
        Check if the given field is in schema and optionally if it's modifiable.

        :param fields:
        :param schema_class:
        :param check_if_modifiable:
        :return:
        """

        key_list = [k for k, v in schema_class.__fields__.items() if not check_if_modifiable or v.field_info.description == "MODIFIABLE"]

        # Only certain fields are considered to be modifiable (description='MODIFIABLE'). Check if the given key
        # corresponds to any of these
        if fields[0] in key_list:

            # was any subfield specified?
            if len(fields) > 1:

                # check if the field has any subfields (is it BaseModel type?)
                if schema_class.__fields__[fields[0]].is_complex() and \
                        lenient_issubclass(schema_class.__fields__[fields[0]].type_, BaseModel):

                    self.__is_in_schema(
                        fields=fields[1:],
                        schema_class=schema_class.__fields__[fields[0]].type_,
                        check_if_modifiable=check_if_modifiable,
                        value=value
                    )
                else:
                    # subfield given but field does not have any subfields
                    raise KeyError(f"Subfield '{fields[1]}' given but field '{fields[0]}' does not have any subfields.")
            else:
                if value is not None \
                        and not lenient_isinstance(value, schema_class.__fields__[fields[0]].type_) \
                        and not lenient_isinstance(value, get_origin(schema_class.__fields__[fields[0]].type_)) \
                        and not lenient_isinstance(value, get_args(schema_class.__fields__[fields[0]].type_)):
                    raise ValueError(f"Given value {value} has wrong type. Expected "
                                     f"{schema_class.__fields__[fields[0]].type_} got {type(value)}.")
        else:
            # given field is not modifiable
            raise KeyError(f"Given field '{fields[0]}' {'is not modifiable or ' if check_if_modifiable else ''}does "
                           f"not exist in the schema.")

    @staticmethod
    def __validate_message(
            message: dict[str, tuple[Callable, Any] | Any],
            access_point: tuple,
            *, to_validate: Any | None = None,
            **conditions
    ) -> tuple[list, list]:
        """
        Validate 'message' against given 'conditions' - when dealing with embedded fields may be necessary to specify
        to_validate as different from the default - 'message'. The method also returns the index of the message. If
        validation failed the method will return empty lists.

        :param message:
        :param index:
        :param to_validate:
        :param conditions:
        :return:
        """

        # default value of to_validate is message, user may want to specify otherwise when validating against values in
        # embedded fields
        to_validate = message if not to_validate else to_validate

        # iterate over conditions
        for key, val in conditions.items():

            # if callable (operator) not given assume it is operator.eq (==)
            if isinstance(val, tuple):
                logical_func, val = val
            else:
                logical_func = operator.eq

            # if any of the conditions is not met break the loop
            if not logical_func(to_validate[key], val):
                return [], []

        else:
            # this block of code is executed if loop was not 'broken'
            return [access_point], [message]

    def get_messages(
            self,
            _cond: dict[str, tuple[Callable, Any] | Any] | None = None,
            *, at: str | None = None,
            **conditions
    ) -> tuple[list[tuple[int, int | None]], list[dict]]:
        """
        Get messages that meet given conditions. If parameter 'at' specified, conditions are presumed to be part of an
        embedded element, such as dictionary or list of dictionaries. The method returns two lists. The second one is a
        list (programmatically made unique) of messages meeting conditions given. The first one is a list of tuples;
        each tuple contains index of the message that met the conditions and - if the 'at' was specified and pointed to
        list/set-type field - an index of subfield that met the condition. Each tuple can be treated as an access point.
        New parameter fname, supports using the dot-notation to point at embedded fields.

        Example:

            _cond={"broadcasted.client_name": "John", "broadcasted.client_connected": True} is equivalent to:
            at="broadcasted", client_name="John", client_connected=True

            _cond={"message_id": "...", "timestamps.server_received": datetime(...), "broadcasted.client_connected": True}
            does not have any equivalent


        :param _cond:
        :param at:
        :param conditions:
        :return: list of indices, list of messages
        """

        if _cond is None:

            # if nothing specified return all messages
            if (at, conditions) == (None, {}):
                return [(i, None) for i in range(len(self.waiting_messages))], self.waiting_messages

            # support for using **conditions and 'at' instead of _cond - convert **conditions and 'at' into _cond
            # dictionary
            _cond = {k if at is None else f"{at}.{k}": v for k, v in conditions.items()}

        # initiate lists for messages that meet all conditions and their indices
        indices: list[tuple[int, int | None]] = []
        messages_found: list[dict] = []

        # iterate over all messages
        for i, message in enumerate(self.waiting_messages):

            # count the number of times the message met the condition, then compare with number of conditions
            passing = 0
            sub_indices = []

            # iterate over conditions
            for key, val in _cond.items():

                # if the input _cond was of the form {'field.path': '...', 'some_field': '...', ...} the convert each
                # value to tuple; i.e. {'field.path': (operator.eq, '...'), 'some_field': (operator.eq, '...'), ...}.
                # Default operator function operator.eq
                if not isinstance(val, tuple):
                    val = (operator.eq, val)

                func, val = val

                # break down the key into names of fields
                field_path = [fname for fname in key.split('.') if fname != '']

                # check if requested fields exist in schema and if their value has an appropriate type
                self.__is_in_schema(
                    fields=field_path,
                    schema_class=self.Schema,
                    check_if_modifiable=False,
                    value=val
                )

                if len(field_path) == 1:
                    # it is 'normal' field without embedding

                    if func(message[field_path[0]], val):
                        passing += 1

                elif len(field_path) == 2:
                    # field with embedding - iterable (list/set) or dict-like

                    if isinstance(message[field_path[0]], (list, set)):
                        # iterable (list/set)

                        for j, elem in enumerate(message[field_path[0]]):

                            if func(message[field_path[0]][j][field_path[1]], val):
                                passing += 1
                                sub_indices.append(j)

                    else:
                        # it is dict-like

                        if func(message[field_path[0]][field_path[1]], val):
                            passing += 1

                else:
                    # if someone specifies another level of embedding, like 'some_field.some_other_field_field' - no
                    # support for that at the moment
                    raise ValueError(f"Cannot convert given string {key} into a valid path to the field.")

            else:
                # after each for-loop iterating over conditions check 'passing' and 'sub_indices' and assess whether to
                # add the message and indices to the list or not
                if passing == len(_cond):
                    messages_found.append(message)
                    if sub_indices:
                        indices += [(i, j) for j in sub_indices]
                    else:
                        indices.append((i, None))

        # remove duplicate messages (by message_id) and access points
        indices = list(set(indices))
        messages_found = list({v["message_id"]: v for v in messages_found}.values())

        return indices, messages_found

    def update_messages(
            self,
            *, field_name: str,
            value: Any,
            at: str | None = None,
            _cond: dict[str, tuple[Callable, Any] | Any] | None = None,
            indices: list[tuple[int, int | None]] | None = None,
            return_indices: bool = False,
            **conditions
    ) -> list[tuple[int, int | None]] | None:
        """
        self.waiting_messages[i][fname] = ... (at = None)
        self.waiting_messages[i][fname1][fname2] = ... (at = fname1, access_points = [(i, None), ...])
        self.waiting_messages[i][fname1][j][fname2] = ... (at = fname1, access_points = [(i, j), ...])

        :param _cond:
        :param field_name:
        :param value:
        :param at:
        :param conditions:
        :return:
        """

        # check if the given field_name corresponds to a modifiable field in the schema and if the value is ok type
        self.__is_in_schema(
            fields=([at] if at else []) + [field_name],
            schema_class=self.Schema,
            check_if_modifiable=True,
            value=value
        )

        if not indices:
            # get access points for the changes to be made
            if _cond:
                access_points, _ = self.get_messages(_cond)
            else:
                access_points, _ = self.get_messages(at=at, **conditions)
        else:
            access_points = indices

        # modify the messages according to three possible cases
        for i, j in access_points:

            if at is not None and j is not None:

                # the field corresponds to a list of dict-like objects
                self.waiting_messages[i][at][j][field_name] = value

            elif at is not None and j is None:

                # the field corresponds to a dict-like object
                self.waiting_messages[i][at][field_name] = value

            else:

                # the field is none of the above and can be directly modified
                self.waiting_messages[i][field_name] = value

        if return_indices:
            return access_points

    def get_not_broadcasted_messages(self, recipient_name: str) -> list[dict | None]:
        """
        Old method. Wraps around get_messages(). It extracts messages with matching recipient name if they are connected
        - the messages that were not sent (client_connected=True, message_sent_at=None).

        :param str recipient_name: client_name
        :return: list of messages not sent to the client
        """

        _, messages = self.get_messages(
            at="broadcasted",
            client_name=recipient_name,
            client_connected=True,
            message_sent_at=None
        )

        return messages

    @staticmethod
    def __validate_string_condition(_str: str) -> tuple[bool, str | None, Optional[Callable], str, str]:
        """
        Validate if a string is condition-format and if so return the operator as a string and corresponding callable
        from operator module.

        Examples:

            'some_variable==whatever'
            return True, '==', operator.eq, 'some_variable', 'whatever'

            'some_variable=whatever'
            return False, None, None, '', ''

            'some_variable>=whatever'
            return True, '>=', operator.ge, 'some_variable', 'whatever'

            'some_variable=='
            return True, '==', operator.eq, 'some_variable', ''

        :return: is_condition, str_condition, logical_func, lhs, rhs
        """

        # list possible allowed operators and corresponding functions
        recognised_logical_operations = [
            ('==', operator.eq),
            ('!=', operator.ne),
            ('>=', operator.ge),
            ('<=', operator.le),
            ('>', operator.gt),
            ('<', operator.lt)
        ]

        # iterate over recognised_logical_operations
        for operator_str, func in recognised_logical_operations:

            # if match found return the tuple
            if operator_str in _str:

                return True, operator_str, func, _str.split(operator_str)[0], _str.split(operator_str)[1]

        else:

            # if not return False and fill up the rest
            return False, None, None, "", ""

    def __str_to_cond_dict(self, query_items: list[str], *values) -> dict[str, tuple[Callable, Any]]:
        """
        Transform list of string of the format:
            query_items = ["some.field=={}", "some_other.field>={}"], values=["some_str", 427.02]
        To dictionary as such:
            {"some.field": (request.eq, "some_str"), "some_other.field": (request.ge, 427.02)}

        :param query_items:
        :param values:
        :return:
        """

        _cond: dict[str, tuple[Callable, Any]] = {}

        # iterate over query_items to extract parameters
        for condition, val in zip(query_items, values):

            # check if the item is valid condition-format and break it down
            is_condition, _, logical_func, field_name, _ = self.__validate_string_condition(condition)

            if is_condition:

                # all good, we can add condition to the dictionary
                _cond[field_name] = (logical_func, val)

            else:

                raise ValueError(f"Non-condition-format ({condition}) found in the query.")

        else:

            return _cond

    def __update_multiple(self, query_items: list[str], values: list, _cond: dict[str, tuple[Callable, Any | None]] | None = None):
        indices = None

        # update each field given separately
        for field, val in zip(query_items, values):
            field = field.split('=')[0]

            parent_field_name = field.split('.')[0] if len(field.split('.')) == 2 else None
            child_field_name = field.split('.')[1] if len(field.split('.')) == 2 else field.split('.')[0]

            indices = self.update_messages(
                at=parent_field_name,
                field_name=child_field_name,
                value=val,
                _cond=_cond,
                indices=indices,
                return_indices=True
            )

    def query(self, _query: str, *, update_val: list | None = None, where_val: list | None = None) -> list[dict] | None:
        """
        Accepts queries in the format:

            GET WHERE <condition1>, <condition2>, ...
                function input: ("GET WHERE <f1><lo1>{}, <f2><lo2>{}, ...", <v1>, <v2>, ...)

            GET ALL
                function input: ("GET ALL")

            UPDATE <field1>, <field2>, ... WHERE <condition1>, <condition2>, ...
                function input: ("UPDATE <f1>={}, <f2>={}, ...
                                  WHERE <f3><lo1>{}, <f4><lo2>{}, ...", <v1>, <v2>, ..., <v3>, <v4>, ...)

            UPDATE ALL <field1>, <field2>, ...
                function input: ("UPDATE ALL <f1>={}, <f2>={}, ...", <v1>, <v2>, ...)

            DELETE WHERE <condition1>, <condition2>, ...
                function input: ("DELETE WHERE <f1><lo1>{}, <f2><lo2>{}, ...", <v1>, <v2>, ...)

            DELETE IN(<field0>) WHERE <condition1>, <condition2>, ...
                function input: ("DELETE IN(<f0>) WHERE <f0.f1><lo1>{}, <f0.f2><lo2>{}, ...", <v1>, <v2>, ...)
                If a field value is a list of dict-like elements the query can be applied to remove one of the elements
                from the list. Conditions here need to apply to the embedded field

            DELETE ALL
                function input: ("DELETE ALL")

            ... WHERE <condition1>, <condition2>, ...
                equivalent to 'AND'

            ... WHERE <condition1> AND <condition2> ...
                both conditions need to be met

            ... WHERE <condition1> OR <condition2> ...
                at least one condition need to be met

            <fn> - field #n
            <lon> - logical operator #n
            <vn> - value #n

        Example:

            GET WHERE client_name=='John', broadcasted.client_name=='Mike', broadcasted.message_sent_at!=None
                > ("GET WHERE client_name=={}, broadcasted.client_name=={}, broadcasted.message_sent_at!={}", "John", "Mike", None)
                > will return messages sent (with message_sent_at not None) from John to Mike

            UPDATE broadcasted.message_sent_at=datetime.now(), message='foo'
            WHERE message_id=='202211012220020000294127000000001'
                > ("UPDATE broadcasted.message_sent_at={}, message={} WHERE message_id=={}", datetime.now(), "foo", "202211012220020000294127000000001")
                > will update fields message and message_sent_at (in the broadcasted field) in messages with given id

            DELETE WHERE timestamps.client_sent<datetime(2022, 11, 21)
                > ("DELETE WHERE timestamps.client_sent<{}", datetime(2022, 11, 21))
                > delete messages sent before 2022-11-21 (yyyy-mm-dd)

        :param str _query: string format query
        :return: list of indices, list of messages if retrieving (see more in get_messages), otherwise None
        """

        # check if only allowed characters are present in the _query
        allowed_characters = re.compile(r'^[A-Za-z,._\-<>=!(){}\s]+')

        if not allowed_characters.match(_query).group() == _query:

            # raise error if not allowed characters
            raise ValueError("Not allowed characters detected in the query.")

        if not (_query.count(',') == _query.count(', ') and _query.count(' ,') == 0):

            # raise error if any ',' is written without space after or with space before it
            raise ValueError("Semicolons must have space after and no space before itself.")

        # replace 'AND' with semicolons
        _query = _query.replace(' AND ', ', ')

        # check if capitalized words are only the allowed_methods
        allowed_methods = ["GET", "UPDATE", "DELETE", "WHERE", "ALL", "IN"]

        for word in _query.split(' '):
            if word.isupper() and word not in allowed_methods:
                raise ValueError

        # first rule out the most basic possibilities
        if "GET ALL" in _query:

            # return all messages
            return self.waiting_messages

        elif "DELETE ALL" in _query:

            # remove all messages
            self.waiting_messages = []

        else:
            # Here we are left with 'GET WHERE ...', 'UPDATE ALL ...', 'UPDATE ... WHERE ...', 'DELETE WHERE ...',
            # 'DELETE IN(...) WHERE ...'

            query_items = _query.split(' ')

            if "GET WHERE " in _query:
                # use get_messages(...)

                # all args are conditions
                _cond = self.__str_to_cond_dict(query_items[2:], *where_val)

                return self.get_messages(_cond)[1]

            elif "UPDATE ALL " in _query:
                # use update_messages(...)

                # no conditions, all args are fields to be updated
                self.__update_multiple(query_items[2:], update_val)

            elif "UPDATE " in _query and " WHERE " in _query:
                # use update_messages(...)

                _cond = self.__str_to_cond_dict(query_items[query_items.index("WHERE") + 1:], *where_val)

                self.__update_multiple(query_items[1:query_items.index("WHERE")], update_val, _cond=_cond)

            elif "DELETE WHERE " in _query:

                _cond = self.__str_to_cond_dict(query_items[2:], *where_val)

                access_points, _ = self.get_messages(_cond)

                if access_points:

                    # extract only message indices and remove duplicates
                    message_indices = list(set(list(zip(*access_points))[0]))

                    for i in sorted(message_indices, reverse=True):
                        del self.waiting_messages[i]

            elif "DELETE IN(" in _query and ") WHERE " in _query:
                # removing an element from an embedded list of elements

                # foi - field of interest - extract whatever is within 'IN'
                foi = query_items[1][3:-1]

                _cond = self.__str_to_cond_dict(query_items[3:], *where_val)

                access_points, _ = self.get_messages(_cond)

                if access_points:

                    # E.g. DELETE IN(broadcasted) WHERE message_id=="..." will remove all stuff from broadcasted list
                    # E.g. DELETE IN(broadcasted) WHERE timestamps.server_received==datetime(...) will also remove all
                    # elements from the list
                    # E.g. DELETE IN(broadcasted) WHERE message_id=="..." AND broadcasted.client_name="..." will remove
                    # the matching element(s) from the broadcasted list
                    if len(set([k.split('.')[0] for k in _cond.keys() if '.' in k])) == 1:
                        # remove one element from the embedded list

                        access_points.reverse()

                        for i, j in access_points:
                            del self.waiting_messages[i][foi][j]

                    else:
                        # clear whole list

                        # extract only message indices and remove duplicates
                        message_indices = list(set(list(zip(*access_points))[0]))

                        for i in sorted(message_indices, reverse=True):
                            self.waiting_messages[i][foi].clear()

            else:

                # some other exception with the query happened
                raise Exception(f"Cannot find an action for given query {_query}")


class SortByDate:
    @staticmethod
    def find_datetime_value_key(_dict: dict) -> list[list[str]] | None:
        key_list = []

        for key, val in _dict.items():

            if isinstance(val, (datetime, date, time)):

                key_list.append([key])

            else:

                # noinspection PyBroadException
                try:

                    # assume the field has embedded dict-like entry
                    for sub_key, sub_val in val.items():

                        if isinstance(sub_val, (datetime, date, time)):

                            key_list.append([key, sub_key])

                except Exception:

                    # if it's not dict-like skip to the next iteration
                    continue

        return key_list

    @staticmethod
    def sort_by_date(_list: list[dict], *keys) -> list:
        """
        Sort list of dictionaries by one of the values. Input can be:
            _list = [
                {"timestamp": 2019-12-20},
                {"timestamp": 2019-10-28},
                {"timestamp": 2020-02-11}
            ]
            keys = ["timestamp"]
        Or:
            _list = [
                {"number": 5},
                {"number": 16},
                {"number": 2}
            ]
            keys = ["number"]
        Or:
            _list = [
                {"foo": {"timestamp": 2019-12-20}},
                {"foo": {"timestamp": 2019-10-28}},
                {"foo": {"timestamp": 2020-02-11}}
            ]
            keys = ["foo", "timestamp"]
        :param _list: list of dictionaries with datetime values (or other types that can be used with sorted())
        :param keys: key of the field ^ (or two keys if the field is embedded)
        :return: sorted list
        """
        # All elements of the keys list must be strings
        if not all([isinstance(key, str) for key in keys]):
            raise TypeError(f"Input keys ({keys}) has incorrect type.")

        return sorted(_list, key=lambda x: x[keys[0]] if len(keys) == 1 else x[keys[0]][keys[1]])


if __name__ == "__main__":
    import pprint as pp

    client_list = ["John", "Mike"]
    recipient_list = ["Mike", "John"]

    message_list = [
        {
            "header": len(bytes("Hello world!", encoding='utf-8')),
            "message_id": f"202211012220{str(i).zfill(2)}000029412700000000{i % 2}",
            "client_name": client_list[i % 2],
            "timestamp": {
                "client_sent": datetime(2022, 11, 1, 22, 20, i, 294),
                "server_received": datetime(2022, 11, 1, 22, 20, i + 1, 1261),
            },
            "message": "Hello world!",
            "client_address": (f"127.0.0.{i % 2}", 5050),
            "broadcasted": [
                {
                    "client_name": recipient_list[i % 2],
                    "client_connected": False,
                    "message_sent_at": None,
                    "message_received_at": None
                }
            ]
        } for i in range(10)
    ]
    mh = MessageHandler(MessageSchema)
    mh.waiting_messages = message_list

    mh.query("GET WHERE client_name==*, broadcasted.client_name==*, broadcasted.message_sent_at!=*", "John", "Mike", None)

