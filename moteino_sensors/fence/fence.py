#!/usr/bin/env python
from threading import Event
import json
import logging
import time

from moteino_sensors import mqtt
from moteino_sensors import utils

class Fence(mqtt.Mqtt):
  def __init__(self, conf):
    super(Fence, self).__init__()
    self.name = 'fence'
    self.enabled = Event()
    self.enabled.set()
    self.conf = conf
    self.mqtt_config = conf['mqtt']
    self.start_mqtt()

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    while True:
      self.enabled.wait()
      req = utils.http_request(self.conf['geo_api'], auth=(self.conf['geo_user'], self.conf['geo_pass']))

      try:
        data = json.loads(req.text)
      except (ValueError, TypeError, AttributeError) as e:
        data = None

      if data:
        self._check_action(data)
      elif self.status.get('armed') == 0:
        self._set_armed()
      time.sleep(self.conf['loop_time'])

  def _check_action(self, data):
    status = {
      'enter': 0,
      'exit': 0,
    }
    for device in data:
      action = data[device]['action']
      if device in self.conf['geo_devices']:
        if self.conf['enter_status'] == action:
          status['enter'] += 1
        elif self.conf['exit_status'] == action:
          status['exit'] += 1

    armed = self.status.get('armed')

    LOG.debug("API data '%s', status '%s', armed %s", data, status, armed)

    if (armed == 1) and (status['enter'] > 0):
      self._unset_armed()
    elif (armed == 0) and (status['exit'] == len(self.conf['geo_devices'])):
      self._set_armed()

  def _set_armed(self):
    LOG.info('Arm alarm')
    self.publish_status({'armed': 1})

  def _unset_armed(self):
    LOG.info('Disarm alarm')
    self.publish_status({'armed': 0})


LOG = logging.getLogger(__name__)


def main():
  parser = utils.create_arg_parser('Fence')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  fence = Fence(conf=conf)
  fence.run()


if __name__ == "__main__":
  main()
