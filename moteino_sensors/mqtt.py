from threading import _Event
import json
import logging
import socket
import time

import paho.mqtt.client as paho

from moteino_sensors import utils

LOG = logging.getLogger(__name__)


class Mqtt(object):

  def __init__(self):
    super(Mqtt, self).__init__()

  def _on_mgmt_status(self, client, userdata, msg):
    status_topic = self.mqtt_config['topic'].get('mgmt/status')
    if not status_topic:
      return

    #Remove 'mgmt/status/' from topic
    status_name = msg.topic[len(status_topic)+1:]
    self.status[status_name] = msg.payload

    if self.name in self.status and hasattr(self, 'enabled'):
      if isinstance(self.enabled, _Event):
        self.enabled.set() if int(self.status[self.name]) else self.enabled.clear()
      else:
        self.enabled = self.status[self.name]

  def _on_connect(self, client, userdata, flags, rc):
    LOG.info('Connection to broker established')
    if 'subscribe_to' in userdata:
      self.subscribe(userdata['subscribe_to'])

  def _on_disconnect(self, client, userdata, rc):
    if rc != 0:
      LOG.error('Connection to broker failed, reconnecting')
      while True:
        try:
          self.mqtt.reconnect()
        except(socket.error) as e:
          time.sleep(5)
        else:
          break

  def _connect(self, server='localhost', port=1883, keepalive=60, retries=-1, use_default_handlers=True):
    while retries != 0:
      try:
        self.mqtt.connect(server, port, keepalive)
      except (socket.error) as e:
        retries -= 1
        LOG.error('Fail to connect to broker, waiting..')
        time.sleep(5)
      else:
        if use_default_handlers:
          self.mqtt.on_connect = self._on_connect
          self.mqtt.on_disconnect = self._on_disconnect
        break

  def start_mqtt(self):
    if not hasattr(self, 'status'):
      self.status = {}

    topic = self.mqtt_config.get('topic', {})
    topic_subscribe = topic.get('subscribe', {})
    subscribe_to = []

    for t in topic_subscribe:
      subscribe_to.append(topic_subscribe[t])

    userdata = {
      'subscribe_to': subscribe_to
    }
    self.mqtt = paho.Client(userdata=userdata, protocol=paho.MQTTv31)
    self._connect(self.mqtt_config['server'])

    for t in topic_subscribe:
      if t == 'mgmt/status':
        self.mqtt.message_callback_add(topic_subscribe[t], self._on_mgmt_status)
      else:
        self.mqtt.message_callback_add(topic_subscribe[t], self._on_message)

  def loop_start(self):
    self.mqtt.loop_start()
    self.mqtt._thread.setName(self.name+'-mqtt')

  def publish_status(self, status=None):
    topic = self.mqtt_config.get('topic', {})
    if hasattr(self, 'status') and 'mgmt/status' in topic:
      if status:
        self.status.update(status)
      else:
        status = self.status
      for status_name in status:
        status_value = self.status[status_name]
        self.publish(topic['mgmt/status'] + '/' + status_name, status_value, retain=True)
        if 'executor/metric' in topic:
          self.publish_metric(topic['executor/metric'], {'sensor_type': 'status_' + status_name,
            'board_id': self.name,
            'sensor_data': status_value
          })
    else:
      LOG.warning('Status topic unknown, not publishing')

  def subscribe(self, topic):
    if isinstance(topic, str) or isinstance(topic, unicode):
      self.mqtt.subscribe(str(topic))
    elif isinstance(topic, list):
      for t in topic:
        self.mqtt.subscribe(str(t))
    else:
      LOG.warning("Fail to subscribe to topic '%s', unknown type", topic)

  def publish_metric(self, topic, payload):
    mqtt_topic = topic + '/' + payload['sensor_type'] + '/' + payload['board_id']
    self.publish(mqtt_topic, payload['sensor_data'])

  def publish(self, topic, payload, retain=False):
    if self.mqtt._host:
      if topic:
        self.mqtt.publish(topic, payload=payload, retain=retain)
      else:
        LOG.warning('Topic is empty')
    else:
      LOG.warning('Client is not connected to broker')
