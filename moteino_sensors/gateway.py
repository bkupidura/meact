#!/usr/bin/env python
from multiprocessing import Process
import Queue
import argparse
import logging
import random
import sqlite3
import sys
import threading
import time

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils


class ActionDetailsAdapter(dict):
  """Adapter for action details

  Provides helpers and functions that allows
  to easily work on action details
  """
  def should_check_if_armed(self, board_id):
    """Should action be checked for given board?"""
    return (
      self['check_if_armed']['default']
      ^
      (board_id in self['check_if_armed']['except'])
    )


class MgwThread(mqtt.MqttThread):
  status = {
    'mgw': 1,
    'msd': 1,
    'srl': 1,
    'armed': 1,
    'fence': 1
  }

  def __init__(self, db_file, boards_map, sensors_map, action_config, mqtt_config):
    super(MgwThread, self).__init__()
    self.name = 'mgw'
    self.enabled = threading.Event()
    self.enabled.set()
    self.action_status = {}
    self.db_file = db_file
    self._db = None
    self.boards_map = boards_map
    self.sensors_map = sensors_map
    self.action_config = action_config
    self.mqtt_config = mqtt_config
    self.action_queue = Queue.Queue()

    self.start_mqtt()

    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/metric', self._on_message_metric)
    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/action', self._on_message_action)

  def _on_message_metric(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    if not self._db:
      self._db = database.connect(self.db_file)

    if not utils.validate_sensor_data(sensor_data):
      LOG.warning("Fail to validate data '%s', ignoring..", sensor_data)
      return

    self._save_sensors_data(sensor_data)
    self.action_queue.put(sensor_data)

  def _on_message_action(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)
    self.action_queue.put(sensor_data)

  def _save_sensors_data(self, data):
    try:
      self._db.execute(
        "INSERT INTO metrics(board_id, sensor_type, data) VALUES(?, ?, ?)",
        (data['board_id'], data['sensor_type'], data['sensor_data'])
      )
      self._db.commit()
    except (sqlite3.IntegrityError) as e:
      LOG.error("Got exception '%' in mgw thread", e)
    except (sqlite3.OperationalError) as e:
      time.sleep(1 + random.random())
      try:
        self._db.commit()
      except (sqlite3.OperationalError) as e:
        LOG.error("Got exception '%' in mgw thread", e)

  def _action_execute(self, data, actions, action_config):
    result = 0

    for a in actions:
      LOG.debug("Action execute '%s'", a)

      action_name = a['name']
      action_func = utils.ACTIONS_MAPPING.get(action_name)
      conf = action_config.get(action_name)

      if not action_func:
        LOG.warning('Unknown action %s', action_name)
        continue

      p = Process(target=action_func.get('func'), args=(data, conf))
      p.start()
      p.join(action_func.get('timeout'))
      if p.is_alive():
        p.terminate()
        status = 255
      else:
        status = p.exitcode

      if status:
        LOG.error("Fail to execute action '%s', exitcode '%d'", action_name, status)
        failback_actions = a.get('failback')
        if failback_actions:
          LOG.debug("Failback '%s'", failback_actions)
          result += self._action_execute(data, failback_actions, action_config)
      else:
        result += 1

    return result

  def _action_helper(self, data, action_details, action_config=None):
    if not action_details:
      LOG.debug("Missing sensor_map for sensor_type '%s'", data['sensor_type'])
      return

    action_details.setdefault('check_if_armed', {'default': True})
    action_details['check_if_armed'].setdefault('except', [])
    action_details.setdefault('action_interval', 0)
    action_details.setdefault('threshold', 'lambda x: True')
    action_details.setdefault('fail_count', 0)
    action_details.setdefault('fail_interval', 600)
    action_details.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')

    if not utils.validate_action_details(action_details):
      LOG.warning("Fail to validate data '%s', ignoring..", action_details)
      return

    action_details = ActionDetailsAdapter(action_details)

    LOG.debug("Action helper '%s' '%s'", data, action_details)
    now = int(time.time())

    self.action_status.setdefault(data['board_id'], {})
    self.action_status[data['board_id']].setdefault(data['sensor_type'], {'last_action': 0, 'last_fail': []})

    self.action_status[data['board_id']][data['sensor_type']]['last_fail'] = \
      [i for i in self.action_status[data['board_id']][data['sensor_type']]['last_fail'] if now - i < action_details['fail_interval']]

    try:
      data['message'] = action_details['message_template'].format(**data)
    except (KeyError) as e:
      LOG.error("Fail to format message '%s' with data '%s' missing key '%s'", action_details['message_template'], data, e)
      return

    if action_details.should_check_if_armed(data['board_id']) and not self.status.get('armed'):
      return

    if not eval(action_details['threshold'])(data['sensor_data']):
      return

    if len(self.action_status[data['board_id']][data['sensor_type']]['last_fail']) <= action_details['fail_count']-1:
      self.action_status[data['board_id']][data['sensor_type']]['last_fail'].append(now)
      return

    if (now - self.action_status[data['board_id']][data['sensor_type']]['last_action'] <= action_details['action_interval']):
      return

    if self._action_execute(data, action_details['action'], action_config):
      self.action_status[data['board_id']][data['sensor_type']]['last_action'] = now

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.publish_status()
    while True:
      self.enabled.wait()
      try:
        sensor_data = self.action_queue.get(True, 5)
      except (Queue.Empty) as e:
        continue

      if not utils.validate_sensor_data(sensor_data):
        LOG.warning("Fail to validate data '%s', ignoring..", sensor_data)
        continue

      sensor_type = sensor_data['sensor_type']
      sensor_config = self.sensors_map.get(sensor_type)

      board_id = sensor_data['board_id']
      sensor_data['board_desc'] = self.boards_map.get(board_id)

      self._action_helper(sensor_data, sensor_config, self.action_config)


LOG = logging.getLogger(__name__)


def main():
  parser = argparse.ArgumentParser(description='Moteino gateway')
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  parser.add_argument('--create-db', required=False, help='Crate mgw database. CAUTION: IT WILL REMOVE OLD DATA', action="store_true")
  parser.add_argument('--sync-db-desc', required=False, help='Sync boards description', action="store_true")
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  sensors_map = utils.load_config(args.dir + '/sensors.config.json')
  boards_map = utils.load_config(args.dir + '/boards.config.json')

  db = database.connect(conf['db_file'])

  if args.create_db:
    database.create_db(db, boards_map)
    print('Database created in {}'.format(conf['db_file']))
    sys.exit(0)

  if args.sync_db_desc:
    database.sync_boards(db, boards_map)
    print('Syned boards in {}'.format(conf['db_file']))
    sys.exit(0)

  utils.create_logger(conf['logging']['level'])

  mgw = MgwThread(
    db_file=conf['db_file'],
    boards_map=boards_map,
    sensors_map=sensors_map,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'])

  mgw.start()


if __name__ == "__main__":
  main()
