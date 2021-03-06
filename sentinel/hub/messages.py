import json
import logging
from enum import Enum

# from channels import Group
from django.contrib.auth import authenticate
from asgiref.sync import async_to_sync

from .models import Hub
from .utils import InvalidLeaf, validate_uuid, InvalidDevice, PermissionDenied, InvalidMessage

logger = logging.getLogger(__name__)


class MessageType(Enum):
    Config = 'CONFIG'
    DeviceStatus = 'DEVICE_STATUS'
    Subscribe = 'SUBSCRIBE'
    Unsubscribe = 'UNSUBSCRIBE'
    DatastoreCreate = 'DATASTORE_CREATE'
    DatastoreDelete = 'DATASTORE_DELETE'
    DatastoreGet = 'DATASTORE_GET'
    DatastoreSet = 'DATASTORE_SET'
    ConditionCreate = 'CONDITION_CREATE'
    ConditionDelete = 'CONDITION_DELETE'
    GetDevice = 'GET_DEVICE'


class Message:
    def __init__(self, data):
        self.data = data

        self.hub = Hub.objects.get(id=data['hub'])
        try:
            self.leaf = self.hub.get_leaf(data['uuid'])
            self.user = self.leaf.get_user()
        except InvalidLeaf as e:
            if self.type != MessageType.Config:
                raise e

    @property
    def type(self):
        return MessageType(self.data['type'])

    @property
    def hub_id(self):
        return self.data['hub']

    def validate(self):
        valid = self.type in MessageType
        if not valid:
            return False
        elif self.type == MessageType.Config:
            valid = valid and 'name' in self.data
            valid = valid and 'model' in self.data
            valid = valid and 'token' in self.data
            valid = valid and 'api_version' in self.data
        elif self.type == MessageType.DeviceStatus:
            valid = valid and 'device' in self.data
            valid = valid and 'mode' in self.data
            valid = valid and 'format' in self.data
            valid = valid and 'value' in self.data
        elif self.type == MessageType.Subscribe or self.type == MessageType.Unsubscribe:
            valid = valid and 'sub_uuid' in self.data and validate_uuid(self.data['sub_uuid'])
            valid = valid and 'sub_device' in self.data
        elif self.type == MessageType.DatastoreCreate:
            valid = valid and 'name' in self.data
            valid = valid and 'value' in self.data
            valid = valid and 'format' in self.data
        elif self.type == MessageType.DatastoreGet:
            return valid and 'name' in self.data
        elif self.type == MessageType.DatastoreSet:
            valid = valid and 'name' in self.data
            valid = valid and 'value' in self.data
        elif self.type == MessageType.DatastoreDelete:
            valid = valid and 'name' in self.data
        elif self.type == MessageType.ConditionCreate:
            valid = valid and 'name' in self.data
            valid = valid and 'predicate' in self.data
            valid = valid and 'actions' in self.data
            if valid and type(self.data['actions']) == list:
                for action in self.data['actions']:
                    valid = valid and 'target' in action
                    valid = valid and 'device' in action
                    valid = valid and 'value' in action
        elif self.type == MessageType.ConditionDelete:
            valid = valid and 'name' in self.data
        else:
            return False
        return valid and 'uuid' in self.data and validate_uuid(self.data['uuid'])

    def reply(self, response):
        pass

    def save_session_info(self, name, value):
        pass

    def register_leaf(self, leaf):
        pass


# class MessageV1(Message):
#     def __init__(self, message):
#         self.session = message.channel_session
#         self.reply_channel = message.reply_channel

#         try:
#             data = json.loads(message.content['text'])
#             data['hub'] = message.channel_session['hub']
#             super().__init__(data)
#         except json.decoder.JSONDecodeError as e:
#             logger.error(f"{self.hub_id} -- Invalid Message: JSON Decoding failed")
#             raise InvalidMessage(e)
#         except InvalidMessage as e:
#             logger.error(f"{self.hub_id} -- Invalid Message: {e}")
#             raise e
#         except (InvalidDevice, InvalidLeaf, PermissionDenied) as e:
#             logger.error(f"{self.hub_id} -- {e} in handling {self.type} for {self.data['uuid']}")
#             reply = e.get_error_message()
#             reply['hub'] = self.hub()
#             self.reply(reply)
#             raise InvalidMessage(e)

#     def save_session_info(self, name, value):
#         self.session[name] = value

#     def reply(self, response):
#         self.reply_channel.send({"text": json.dumps(response)})

#     def register_leaf(self, leaf):
#         Group(f"{leaf.hub.id}-{leaf.uuid}").add(self.reply_channel)

#     def unregister_leaf(self, leaf):
#         Group(f"{leaf.hub.id}-{leaf.uuid}").discard(self.reply_channel)


class MessageV2(Message):
    def __init__(self, consumer, message):
        self.session = consumer.scope["session"]
        self.consumer = consumer

        try:
            message['hub'] = self.session['hub']
            super().__init__(message)
        except json.decoder.JSONDecodeError as e:
            logger.error(f"{self.hub_id} -- Invalid Message: JSON Decoding failed")
            raise InvalidMessage(e)
        except InvalidMessage as e:
            logger.error(f"{self.hub_id} -- Invalid Message: {e}")
            raise e
        except (InvalidDevice, InvalidLeaf, PermissionDenied) as e:
            logger.error(f"{self.hub_id} -- {e} in handling {self.type} for {self.data['uuid']}")
            reply = e.get_error_message()
            reply['hub'] = self.hub()
            self.reply(reply)
            raise InvalidMessage(e)

    def save_session_info(self, name, value):
        self.session[name] = value
    
    def get_session_info(self, name):
        return self.session[name]

    def reply(self, response):
        self.consumer.send_json(response)

    def register_leaf(self, leaf):
        async_to_sync(self.consumer.channel_layer.group_add)(f"{leaf.hub.id}-{leaf.uuid}", self.consumer.channel_name)

    def unregister_leaf(self, leaf):
        async_to_sync(self.consumer.channel_layer.group_discard)(f"{leaf.hub.id}-{leaf.uuid}", self.consumer.channel_name)
