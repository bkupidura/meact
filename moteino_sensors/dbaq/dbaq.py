#!/usr/bin/env python
import abc
import argparse
import logging
import threading
import time

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils

class DBQueryThread(mqtt.MqttThread):
  __metaclass__ = abc.ABCMeta

  name = None

  def __init__(self, conf):
    super(DBQueryThread, self).__init__()
    self.enabled = threading.Event()
    self.enabled.set()
    self.loop_sleep = conf[self.name]['loop_sleep']
    self.db_file = conf['db_file']
    self.query = conf[self.name]['query']
    self.mqtt_config = conf['mqtt']

    self.start_mqtt()

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.db = database.connect(self.db_file)
    
    while True:
      self.enabled.wait()

      result = self.db.execute(self.query)
      self._handle_query_result(result)

      time.sleep(self.loop_sleep)

  def _handle_query_result(self, query_result):
      for board_id, value in query_result:
        self._handle_result(board_id, value)

  @abc.abstractmethod
  def _handle_result(self, board_id, value):
    pass

class MsdThread(DBQueryThread):

  name = 'msd'

  def _handle_result(self, board_id, value):
    now = int(time.time())
    data = {'board_id': board_id,
            'sensor_data': str(now - value),
            'sensor_type': self.name}
    self.publish(self.mqtt_config['topic']['exc'], data)


LOG = logging.getLogger(__name__)


def main():
  parser = argparse.ArgumentParser(description='DBAQ - database asynchronous query')
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')

  utils.create_logger(logging.INFO)

  msd = MsdThread(conf=conf)
  msd.start()


if __name__ == "__main__":
  main()
