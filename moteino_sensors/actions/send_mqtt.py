import logging
import sys

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
    "topic": "topic",
    "message": ["message", "message {board_id}"],
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending message over MQTT')

  mqtt_details = {
    'topic': action_config['topic'],
    'qos': action_config.get('qos', 0),
    'retain': action_config.get('retain', False),
    'hostname': action_config.get('hostname', 'localhost'),
    'port': action_config.get('port', 1883),
    'auth': action_config.get('auth', None)
  }

  for m in action_config['message']:
    try:
      m = m.format(**data)
    except (KeyError, ValueError) as e:
      LOG.warning("Fail to format message '%s' with data '%s'", m, data)
      continue

    publish.single(mqtt_details['topic'],
            payload=m,
            qos=mqtt_details['qos'],
            retain=mqtt_details['retain'],
            hostname=mqtt_details['hostname'],
            port=mqtt_details['port'],
            auth=mqtt_details['auth'])

  sys.exit(0)
