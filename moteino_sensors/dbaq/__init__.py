#!/usr/bin/env python
from threading import Event
import abc
import logging
import time


from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils

LOG = logging.getLogger(__name__)

class DBQuery(mqtt.Mqtt):
  __metaclass__ = abc.ABCMeta

  name = None

  def __init__(self, conf):
    super(DBQuery, self).__init__()
    self.enabled = Event()
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
