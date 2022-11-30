from pydantic import BaseModel, validator, Extra, Field
from datetime import datetime
from typing import Tuple, TypeVar, Any


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

    return False


def get_message_id(message_id: str, values: dict) -> str:
    # generate message id from the first-found timestamp and sender ip address
    if not message_id:

        # get values of the time and sender ip
        timestamp: datetime = list(values['timestamps'].dict().values())[0]
        _ip: str = list(filter(is_addr_type, values.values()))[0][0]

        # combine timestamp with client IP address to form most likely unique ID. Assumption: client cannot send two
        # messages at the same time.
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S%f")
        _ip_str = "".join(list(map(lambda x: x.zfill(3), _ip.split('.'))))

        return timestamp_str + _ip_str
    else:
        return message_id


class UserStatus(BaseModel):
    client_name: str
    client_connected: bool = Field(description="MODIFIABLE")
    message_sent_at: datetime | None = Field(None, description="MODIFIABLE")
    message_received_at: datetime | None = Field(None, description="MODIFIABLE")

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


class OneWayTimestamp(BaseModel):
    message_created: datetime = Field(default_factory=lambda: datetime.now())

    class Config:
        extra = Extra.forbid


class ServerClientCommunicationSchema(BaseModel):
    header: int
    timestamps: OneWayTimestamp
    message: str
    client_address: AddrType
    broadcasted: list[UserStatus] = Field(description="MODIFIABLE")
    message_id: str | None = None

    @validator('client_address')
    def must_be_ipv4(cls, v) -> AddrType:
        if is_addr_type(v):
            return v
        else:
            raise ValueError("Given tuple does not meet AddrType requirements. "
                             "Check schema definition for more details.")

    class Config:
        extra = Extra.forbid


registered_classes = (UserStatus, Timestamp, MessageSchema, OneWayTimestamp, ServerClientCommunicationSchema)


if __name__ == "__main__":
    for cls in registered_classes:
        import pprint as pp

        print(cls.__name__)
        for k, v in cls.__fields__.items():
            pp.pprint(f"{k}: {v}")#, description={v.field_info.description}")
        print('\n')
