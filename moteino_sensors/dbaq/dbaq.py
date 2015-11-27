#!/usr/bin/env python
import abc
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
    self.db_string = conf['db_string']
    self.query = conf[self.name]['query']
    self.mqtt_config = conf['mqtt']

    self.start_mqtt()

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.db = database.connect(self.db_string)
    
    while True:
      self.enabled.wait()

      result = self.db.execute(self.query)
      self._handle_query_result(result)

      time.sleep(self.loop_sleep)

  def _handle_query_result(self, query_result):
      for board_id, value in query_result:
        LOG.debug("Got query result (%s) for board '%s' value '%s'", self.name, board_id, value)
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
    self.publish(self.mqtt_config['topic']['mgw']+"/action", data)


LOG = logging.getLogger(__name__)


def main():
  parser = utils.create_arg_parser('DBAQ - database asynchronous query')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  msd = MsdThread(conf=conf)
  msd.start()


if __name__ == "__main__":
  main()
