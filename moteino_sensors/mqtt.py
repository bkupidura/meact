import json
import socket
import time
import logging
import threading
import paho.mqtt.client as paho
import paho.mqtt.publish as paho_publish

from moteino_sensors import utils

LOG = logging.getLogger(__name__)

def subscribe(client, topic):
  if isinstance(topic, str) or isinstance(topic, unicode):
    client.subscribe(str(topic))
  elif isinstance(topic, list):
    for t in topic:
      client.subscribe(str(t))
  else:
    LOG.warning("Fail to subscribe to topic '%s', unknown type", topic)

def publish(client, topic, payload, retain=False):
  payload = json.dumps(payload)
  if client._host:
    client.publish(topic, payload=payload, retain=retain)
  else:
    LOG.warning('Client is not connected to broker')

def single(topic, payload, retain=False, server='localhost', port=1883, keepalive=60):
  payload = json.dumps(payload)
  paho_publish.single(topic, payload=payload, retain=retain, hostname=server, port=port, keepalive=keepalive)

def connect(client, server='localhost', port=1883, keepalive=60, retries=-1, use_default_handlers=True):
  while retries != 0:
    try:
      client.connect(server, port, keepalive)
    except (socket.error) as e:
      retries -= 1
      LOG.error('Fail to connect to broker, waiting..')
      time.sleep(5)
    else:
      if use_default_handlers:
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
      break


def on_connect(client, userdata, flags, rc):
  LOG.info('Connected to broker')
  if 'subscribe_to' in userdata:
    subscribe(client, userdata['subscribe_to'])


def on_disconnect(client, userdata, rc):
  if rc != 0:
    LOG.error('Connection to broker failed, reconnecting')
    while True:
      try:
        client.reconnect()
      except(socket.error) as e:
        time.sleep(5)
      else:
        break

class MqttThread(threading.Thread):

  def __init__(self):
    super(MqttThread, self).__init__()

  def start_mqtt(self):
    if not hasattr(self, 'status'):
      self.status = {}

    topic = self.mqtt_config.get('topic', {})
    subscribe_to = []

    if self.name in topic:
      subscribe_to.append(topic[self.name]+'/#')
    if 'mgmt' in topic:
      subscribe_to.append(topic['mgmt']+'/status')

    userdata = {
      'subscribe_to': subscribe_to
    }
    self.mqtt = paho.Client(userdata=userdata)
    connect(self.mqtt, self.mqtt_config['server'])

    if 'mgmt' in topic:
      self.mqtt.message_callback_add(topic['mgmt']+'/status', self.on_mgmt_status)

  def publish_status(self, status=None):
    topic = self.mqtt_config.get('topic', {})
    if hasattr(self, 'status') and 'mgmt' in topic:
      if status:
        self.status.update(status)
      publish(self.mqtt, topic['mgmt']+'/status', self.status, retain=True)

  def on_mgmt_status(self, client, userdata, msg):
    self.status = utils.load_json(msg.payload)
    if self.name in self.status and hasattr(self, 'enabled'):
      if isinstance(self.enabled, threading._Event):
        self.enabled.set() if self.status[self.name] else self.enabled.clear()
      else:
        self.enabled = self.status[self.name]
