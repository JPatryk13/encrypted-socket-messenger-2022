from pydantic import BaseModel, validator, Extra, Field, root_validator
from pydantic.utils import lenient_issubclass, lenient_isinstance
from datetime import datetime
from typing import Tuple, TypeVar, Any
import pickle
from src.shared_enum_vars import ServerResponseTypes


AddrType = TypeVar('AddrType', bound=Tuple[str, int])


def is_ipv4(_str: str) -> bool:
    # does it contain commas?
    if '.' in _str:

        # does it contain three commas?
        if len(_str.split('.')) == 4:

            # does each segment contain only digits?
            if _str.replace('.', '').isdigit():

                return True

    return False


def is_addr_type(var: Any) -> bool:
    # is it a tuple?
    if isinstance(var, tuple):

        # does it have two elements?
        if len(var) == 2:

            # is first element a string and the second one an integer?
            if isinstance(var[0], str) and isinstance(var[1], int):

                # is the string a correct ipv4 format?
                if is_ipv4(var[0]):

                    return True

    # is it a serialized tuple?
    elif isinstance(var, bytes):
        # it is bytes type, try to convert it to python object
        try:

            # try to convert it to python object
            addr = pickle.loads(var)

        except Exception as err:

            return False

        else:

            # it is python object, rerun the test
            return is_addr_type(addr)

    return False


def get_timestamp_value(values: dict) -> datetime:
    # filter in only datetime type values
    datetime_type_values = list(filter(lambda x: isinstance(x, datetime), list(values.values())))

    if datetime_type_values:
        # if there are any datetime type values, select the first one
        return datetime_type_values[0]
    else:
        # if there are none, check embedded fields

        # filter in only child classes of BaseModel or dicts (embedded fields)
        embedded_fields = list(filter(lambda v: lenient_isinstance(v, (BaseModel, dict)), list(values.values())))

        # convert any BaseModel class to dict, leave out embedded fields that are dictionaries already
        embedded_fields = list(map(lambda d: d.dict() if lenient_isinstance(d, BaseModel) else d, embedded_fields))

        if embedded_fields:

            # rerun the method with embedded dictionary
            return get_timestamp_value(embedded_fields[0])

        else:

            raise Exception("No datetime field found.")


def get_message_id(message_id: str | None, values: dict) -> str:
    # generate message id from the first-found timestamp and sender ip address
    if message_id is None:

        # get values of the time and sender ip
        timestamp = get_timestamp_value(values)
        addr: str = list(filter(is_addr_type, values.values()))[0]

        # combine timestamp with client IP address to form most likely unique ID. Assumption: client cannot send two
        # messages at the same time.
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S%f")
        _ip_str = "".join(list(map(lambda x: x.zfill(3), addr[0].split('.'))))

        return timestamp_str + _ip_str + str(addr[1]).zfill(6)
    else:
        return message_id


class UserStatus(BaseModel):
    client_name: str | bytes
    # client_connected: bool = Field(description="MODIFIABLE")
    message_sent_at: datetime | None = Field(None, description="MODIFIABLE")
    message_received_at: datetime | None = Field(None, description="MODIFIABLE")

    @validator('client_name')
    def must_be_ipv4_or_str(cls, v) -> str | bytes:
        if isinstance(v, str):
            # if it's a string (actual client_name) don't do anything
            return v
        else:

            # it is bytes type, run is_addr_type()
            if is_addr_type(v):
                return v
            else:
                raise ValueError("Given tuple does not meet AddrType requirements. "
                                 "Check schema definition for more details.")

    class Config:
        extra = Extra.forbid


class Timestamp(BaseModel):
    client_sent: datetime
    server_received: datetime = Field(default_factory=lambda: datetime.now())

    class Config:
        extra = Extra.forbid


class MessageSchema(BaseModel):
    """
    Only client_name and message is sent by the client. Server adds timestamp, client_address, broadcasted and
    message_id. The broadcasted list stores usernames (client_name), status (user_connected) and weather the message was
    received by the user or not (message_received) coupled in a dictionary (UserStatus). The message_id is "not
    explicitly" combination of timestamp and client ip.
    """
    header: int
    client_name: str
    timestamps: Timestamp
    message: str  # = Field(description="MODIFIABLE")  # - tests
    client_address: AddrType
    broadcasted: list[UserStatus] = Field(description="MODIFIABLE")
    message_id: str | None

    # validators
    _get_message_id = validator('message_id', allow_reuse=True)(get_message_id)

    @validator('client_address')
    def must_be_ipv4(cls, v) -> AddrType:
        if is_addr_type(v):
            return v
        else:
            raise ValueError("Given tuple does not meet AddrType requirements. "
                             "Check schema definition for more details.")

    class Config:
        extra = Extra.forbid


class ServerClientCommunicationSchema(BaseModel):
    response_type: ServerResponseTypes

    # When response type is CLIENT_CONNECTED.value or CLIENT_DISCONNECTED.value the info should be provided to inform
    # other clients about the one who joined/left
    info: str | None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    broadcasted: list[UserStatus] = Field(description="MODIFIABLE")
    server_addr: AddrType
    message_id: str | None = None

    @validator('server_addr')
    def validate_server_addr(cls, v):
        if is_addr_type(v):
            return v
        else:
            raise ValueError("Given tuple does not meet AddrType requirements. "
                             "Check schema definition for more details.")

    @root_validator
    def get_message_id_from_server_addr(cls, values):
        values["message_id"] = get_message_id(
            None,
            {
                "created_at": values["created_at"],
                "server_addr": values["server_addr"]
            }
        )
        return values

    class Config:
        extra = Extra.forbid


if __name__ == "__main__":
    registered_classes = (UserStatus, Timestamp, MessageSchema, ServerClientCommunicationSchema)

    for cls in registered_classes:
        import pprint as pp

        print(cls.__name__)
        for k, v in cls.__fields__.items():
            pp.pprint(f"{k}: {v}")#, description={v.field_info.description}")
        print('\n')

