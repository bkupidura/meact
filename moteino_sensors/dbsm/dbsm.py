#!/usr/bin/env python
from threading import Event
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

    self.start_mqtt()

    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/metric', self._on_message_metric)

  def _on_message_metric(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    sensor_data = self._prepare_sensor_data(sensor_data)

    LOG.debug("Got new metric '%s'", sensor_data)

    self._save_sensors_data(sensor_data)

  def _save_sensors_data(self, sensor_data):
    if not sensor_data:
      return

    database.insert_metric(self.db, sensor_data)

  def _prepare_sensor_data(self, sensor_data):
    if not utils.validate_sensor_data(sensor_data):
      LOG.warning("Fail to validate data '%s', ignoring..", sensor_data)
      return None

    return sensor_data

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    while True:
      self.enabled.wait()
      time.sleep(0.5)


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
