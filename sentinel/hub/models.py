from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from polymorphic.models import PolymorphicModel
from channels import Group
import json


class Value(PolymorphicModel):
    name = models.CharField(max_length=30)

    def __repr__(self):
        return str(self.value)


class StringValue(Value):
    value = models.CharField(max_length=250)

    @property
    def format(self):
        return "string"


class NumberValue(Value):
    value = models.DecimalField(max_digits=15, decimal_places=4)

    @property
    def format(self):
        return "number"


class UnitValue(Value):
    value = models.DecimalField(max_digits=15, decimal_places=4)
    units = models.CharField(max_length=10)

    @property
    def format(self):
        return "number+units"

    def __repr__(self):
        return "{}{}".format(self.value, self.units)


class BooleanValue(Value):
    value = models.BooleanField()

    @property
    def format(self):
        return "bool"


class Leaf(models.Model):
    # TODO: integrate with authentication, user
    hub_id = 1
    name = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    uuid = models.CharField(primary_key=True, max_length=36)
    api_version = models.CharField(max_length=10, default="0.1.0")
    isConnected = models.BooleanField(default=True)

    def set_name(self, name):
        message = self.message_template
        message["type"] = "SET_NAME"
        message["name"] = name
        self.send_message(message)

    def set_option(self, device, option, value):
        message = self.message_template
        message["type"] = "SET_OPTION"
        message["device"] = device
        message["option"] = option
        message["value"] = value
        self.send_message(message)

    def set_output(self, device, value):
        message = self.message_template
        message["type"] = "SET_OUTPUT"
        message["device"] = device
        message["value"] = value
        self.send_message(message)

    def get_option(self, device, option, update=True):
        if update:
            self.refresh_option(device, option)
        # TODO: Replace following code with real code, add option
        return self.get_device(device, update=False).option_set.filter(name=option)

    def get_options(self, device, update=True):
        if update:
            self.refresh_options()
        return self.get_device(device, update=False).option_set.all()

    def get_device(self, device, update=True):
        if update:
            self.refresh_device(device)
        return self.devices.get(name=device)

    def get_devices(self, update=True):
        if update:
            self.refresh_devices()

        devices = {}
        for device in self.devices.all():
                devices[device.name] = device

        return devices

    def get_name(self):
        return self.name

    def refresh_devices(self):
        message = self.message_template
        message["type"] = "LIST_DEVICES"
        self.send_message(message)

    def refresh_name(self):
        message = self.message_template
        message["type"] = "GET_NAME"
        self.send_message(message)

    def refresh_options(self):
        message = self.message_template
        message["type"] = "LIST_OPTIONS"
        self.send_message(message)

    def refresh_device(self, device):
        message = self.message_template
        message["type"] = "GET_DEVICE"
        message["device"] = device
        self.send_message(message)

    def refresh_option(self, device, option):
        message = self.message_template
        message["type"] = "GET_OPTION"
        message["option"] = option
        message["device"] = device
        self.send_message(message)

    def send_message(self, message):
        message = {"text": json.dumps(message)}
        Group(self.uuid).send(message)

    def create_device(self, device_name, format):
        if format == 'bool':
            device = BooleanDevice(name=device_name, leaf=self, value=False)
        elif format == 'number+units':
            device = UnitDevice(name=device_name, leaf=self, value=0, units="None")
        elif format == 'number':
            device = NumberDevice(name=device_name, leaf=self, value=0)
        else:
            # treat unknown formats as strings per API
            device = StringDevice(name=device_name, leaf=self, value="")
        return device

    def send_subscriber_update(self, device):
        seen_devices = set()
        message = device.status_update_dict

        subscriptions = Subscription.objects.filter(target_uuid=self.uuid)
        for subscription in subscriptions.filter(target_device=device.name):
            seen_devices.add(subscription.subscriber_uuid)
            subscription.handle_update(self.uuid, device.name, message)
        # send messages to whole leaf subscribers
        for subscription in subscriptions.filter(target_device="leaf"):
            if subscription.subscriber_uuid not in seen_devices:
                subscription.handle_update(self.uuid, 'leaf', message)

    @property
    def message_template(self):
        return {"uuid": self.uuid, "hub_id": self.hub_id}

    def __repr__(self):
        return "Leaf <name: {}, uuid:{}>".format(self.name, self.uuid)

    def __str__(self):
        return repr(self)

    @classmethod
    def create_from_message(cls, message):
        model = message['model']
        name = message['name']
        api = message['api_version']
        uuid = message['uuid']
        leaf = cls(name=name, model=model, uuid=uuid, api_version=api)
        leaf.save()
        return leaf


class Device(PolymorphicModel):
    name = models.CharField(max_length=100)
    leaf = models.ForeignKey(Leaf, related_name='devices', on_delete=models.CASCADE)
    is_input = models.BooleanField(default=True)
    _value = models.OneToOneField(Value, on_delete=models.CASCADE, related_name="device")

    @property
    def value(self):
        return self._value.value

    @value.setter
    def value(self, new_value):
        self._value.value = new_value
        self._value.save()
        self.leaf.send_subscriber_update(self)

    @property
    def status_update_dict(self):
        status_update = {
            'type': 'DEVICE_STATUS',
            'uuid': self.leaf.uuid,
            'device': self.name,
            'value': self.value,
            'format': self.format,
        }
        if self.format == 'units':
            status_update['units'] = self._value.units
        return status_update

    def __str__(self):
        return repr(self)

    def refresh_from_db(self, using=None, fields=None):
        self._value.refresh_from_db()
        return super().refresh_from_db(using=using, fields=fields)

    @staticmethod
    def create_from_message(message, uuid=None):
        try:
            if not uuid:
                uuid = message['uuid']
            leaf = Leaf.objects.get(pk=uuid)
        except ObjectDoesNotExist:
            return
        except KeyError:
            return

        is_input = message['mode'].upper() == 'IN'

        format = message['format'].lower()
        if format == 'number':
            value = NumberValue(value=message['value'])
        elif format == 'number+units':
            value = UnitValue(value=message['value'], units=message['units'])
        elif format == 'bool':
            value = BooleanValue(value=message['value'])
        else:
            value = StringValue(value=message['value'])
        value.save()

        device = Device(name=message['device'], _value=value, is_input=is_input, leaf=leaf)
        device.save()
        return device

    @staticmethod
    def create_from_device_list(message):
        uuid = message['uuid']
        for device in message['devices']:
            Device.create_from_message(device, uuid)

    @property
    def format(self):
        return self._value.format

    def __repr__(self):
        return "<Device name:{}, value: {}>".format(self.name, repr(self.value))


class Subscription(models.Model):
    subscriber_uuid = models.CharField(max_length=36)
    target_uuid = models.CharField(max_length=36)
    target_device = models.CharField(max_length=100)

    def handle_update(self, uuid, device, message):
        sub_message = {'type': 'SUBSCRIPTION_UPDATE',
                       'sub_uuid': uuid,
                       'sub_device': device,
                       'message': message}
        Group(self.subscriber_uuid).send({'text': json.dumps(sub_message)})
