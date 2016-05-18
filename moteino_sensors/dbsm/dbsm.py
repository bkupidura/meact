#!/usr/bin/env python
from threading import Event
import Queue
import logging
import sys
import time

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils


class Dbsm(mqtt.Mqtt):
  def __init__(self, db_string, mqtt_config):
    super(Dbsm, self).__init__()
    self.name = 'dbsm'
    self.enabled = Event()
    self.enabled.set()
    self.db = database.connect(db_string)
    self.mqtt_config = mqtt_config
    self.metric_queue = Queue.Queue()

    self.start_mqtt()

  def _on_message(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    sensor_data = self._prepare_sensor_data(sensor_data)

    if sensor_data:
      self.metric_queue.put(sensor_data)

  def _prepare_sensor_data(self, sensor_data):
    validation_result, sensor_data = utils.validate_sensor_data(sensor_data)
    if not validation_result:
      return None

    return sensor_data

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    while True:
      self.enabled.wait()
      try:
        sensor_data = self.metric_queue.get(True, 5)
      except (Queue.Empty) as e:
        continue

      LOG.debug("Got new metric '%s'", sensor_data)

      database.insert_metric(self.db, sensor_data)


LOG = logging.getLogger(__name__)

def main():
  parser = utils.create_arg_parser('DBSM - Database Save Metric')
  parser.add_argument('--create-db', required=False, help='Crate mgw database. CAUTION: IT WILL REMOVE OLD DATA', action="store_true")
  parser.add_argument('--sync-db-desc', required=False, help='Sync boards description', action="store_true")
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  boards_map = utils.load_config(args.dir + '/boards.config.json')

  db = database.connect(conf['db_string'])

  if args.create_db:
    database.create_db(db, boards_map)
    print('Database created in {}'.format(conf['db_string']))
    sys.exit(0)

  if args.sync_db_desc:
    database.sync_boards(db, boards_map)
    print('Syned boards in {}'.format(conf['db_string']))
    sys.exit(0)

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  mgw = Dbsm(
    db_string=conf['db_string'],
    mqtt_config=conf['mqtt'])

  mgw.run()


if __name__ == "__main__":
  main()
