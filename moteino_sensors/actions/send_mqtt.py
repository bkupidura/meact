import logging
import sys

import paho.mqtt.client as paho
import paho.mqtt.publish as publish

from moteino_sensors import utils

LOG = logging.getLogger(__name__)
TIMEOUT=5


def send_mqtt(data, action_config):
  """Send message over MQTT

  In message you can use variables, the same as with
  message_template.

  Ex. '{sensor_type}:enabled'


  MGW configuration:
  action_config = {
    "server": "localhost",
    "port": 1883,
    "message": [{"topic": "topic_name", "message": "message {board_id}", "retain": 0}],
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending message over MQTT')

  mqtt_details = {
    'qos': action_config.get('qos', 0),
    'hostname': action_config.get('hostname', 'localhost'),
    'port': action_config.get('port', 1883),
    'auth': action_config.get('auth', None)
  }

  for m in action_config['message']:
    try:
      topic = m['topic'].format(**data)
      message = m['message'].format(**data)
      retain = m.get('retain', False)
    except (KeyError, ValueError) as e:
      LOG.warning("Fail to format message with data '%s'", data)
      continue

    publish.single(topic,
            payload=message,
            retain=retain,
            qos=mqtt_details['qos'],
            hostname=mqtt_details['hostname'],
            port=mqtt_details['port'],
            auth=mqtt_details['auth'],
            protocol=paho.MQTTv31)

  sys.exit(0)
