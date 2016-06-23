#!/usr/bin/env python
from threading import Event
import json
import logging
import re
import time

import serial

from moteino_sensors import mqtt
from moteino_sensors import utils

class Srl(mqtt.Mqtt):
  def __init__(self, serial, mqtt_config, re_sensor_data):
    super(Srl, self).__init__()
    self.name = 'srl'
    self.enabled = Event()
    self.enabled.set()
    self.status = {'srl': 1}
    self.serial = serial
    self.mqtt_config = mqtt_config
    self._re_sensor_data = re.compile(re_sensor_data)
    self.start_mqtt()

  def _on_message(self, client, userdata, msg):
    try:
      data = json.loads(msg.payload)
    except (ValueError, TypeError):
      data = msg.payload

    data = str(data)

    LOG.debug("Got data for serial '%s'", data)
    try:
      self.serial.write(data)
    except (IOError, ValueError, TypeError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%s' in srl thread", e)

  def _read_sensors_data(self):
    data = {}
    try:
      s_data = self.serial.readline().strip()
      m = self._re_sensor_data.match(s_data)
      # {"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
      data = m.groupdict()
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%' in srl thread", e)
      self.serial.close()
      time.sleep(5)
      try:
        self.serial.open()
      except (OSError) as e:
        LOG.warning('Failed to open serial')
    except (AttributeError) as e:
      if len(s_data) > 0:
        LOG.debug('> %s', s_data)

    return data

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.publish_status()

    while True:
      self.enabled.wait()

      sensor_data = self._read_sensors_data()
      if not sensor_data:
        continue

      LOG.debug("Got data from serial '%s'", sensor_data)
      self.publish_metric(self.mqtt_config['topic']['dbsm/metric'], sensor_data)


LOG = logging.getLogger(__name__)

def main():
  parser = utils.create_arg_parser('SRL - mgw serial')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.yaml')
  conf = conf.get('srl', {})

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  ser = serial.Serial(
    conf['serial']['device'],
    conf['serial']['speed'],
    timeout=conf['serial']['timeout']
  )
  srl = Srl(
    serial=ser,
    mqtt_config=conf['mqtt'],
    re_sensor_data=conf['re_sensor_data'])
  srl.run()


if __name__ == "__main__":
  main()
