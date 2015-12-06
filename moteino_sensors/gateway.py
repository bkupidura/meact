#!/usr/bin/env python
from multiprocessing import Process
import Queue
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
  def build_defaults(self, index):
    self.setdefault('check_if_armed', {'default': True})
    self.setdefault('action_interval', 0)
    self.setdefault('threshold', 'lambda x: True')
    self.setdefault('fail_count', 0)
    self.setdefault('fail_interval', 600)
    self.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')

    self['check_if_armed'].setdefault('except', [])
    self['index'] = index

  def should_check_if_armed(self, board_id):
    """Should action be checked for given board?"""
    return (
      self['check_if_armed']['default']
      ^
      (board_id in self['check_if_armed']['except'])
    )


class ActionStatusAdapter(dict):
  """Adapter for action status

  Provider helpers and functions that allows
  to easily work with action status
  """
  def build_defaults(self, board_id, index, sensor_type):
    self.setdefault(board_id, {})
    self[board_id].setdefault(index, {})
    self[board_id][index].setdefault(sensor_type, {'last_action': 0, 'last_fail': []})

  def clean_failed(self, board_id, index, sensor_type, fail_interval):
    now = int(time.time())
    self[board_id][index][sensor_type]['last_fail'] = \
      [i for i in self[board_id][index][sensor_type]['last_fail'] if now - i < fail_interval]

  def check_failed_count(self, board_id, index, sensor_type, fail_count):
    now = int(time.time())
    failed = self[board_id][index][sensor_type]['last_fail']
    if len(failed) <= fail_count - 1:
      self[board_id][index][sensor_type]['last_fail'].append(now)
      return False
    return True

  def check_last_action(self, board_id, index, sensor_type, action_interval):
    now = int(time.time())
    last_action = self[board_id][index][sensor_type]['last_action']
    if now - last_action <= action_interval:
      return False
    return True

  def update_last_action(self, board_id, index, sensor_type):
    now = int(time.time())
    self[board_id][index][sensor_type]['last_action'] = now


class MgwThread(mqtt.MqttThread):
  status = {
    'mgw': 1,
    'msd': 1,
    'srl': 1,
    'armed': 1,
    'fence': 1
  }

  def __init__(self, db_string, boards_map, sensors_map, action_config, mqtt_config):
    super(MgwThread, self).__init__()
    self.name = 'mgw'
    self.enabled = threading.Event()
    self.enabled.set()
    self.action_status = ActionStatusAdapter()
    self.db = database.connect(db_string)
    self.boards_map = boards_map
    self.sensors_map = sensors_map
    self.action_config = action_config
    self.mqtt_config = mqtt_config
    self.action_queue = Queue.PriorityQueue()

    self.start_mqtt()

    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/metric', self._on_message_metric)
    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/action', self._on_message_action)

  def _on_message_metric(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    sensor_data, sensor_config = self._prepare_data(sensor_data)

    self._save_sensors_data(sensor_data)
    self._put_in_queue(sensor_data, sensor_config)

  def _on_message_action(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    sensor_data, sensor_config = self._prepare_data(sensor_data)

    self._put_in_queue(sensor_data, sensor_config)

  def _save_sensors_data(self, sensor_data):
    if not sensor_data:
      return

    database.insert_metric(self.db, sensor_data)

  def _put_in_queue(self, sensor_data, sensor_config):
    if not sensor_data or not sensor_config:
      return

    if not 'priority' in sensor_config or not isinstance(sensor_config['priority'], int):
      priority = 500
    else:
      priority = sensor_config['priority']

    self.action_queue.put((priority, sensor_data, sensor_config))

  def _prepare_data(self, sensor_data):
    sensor_data = self._prepare_sensor_data(sensor_data)
    sensor_config = self._prepare_action_details(sensor_data)

    return sensor_data, sensor_config

  def _prepare_sensor_data(self, sensor_data):
    if not utils.validate_sensor_data(sensor_data):
      LOG.warning("Fail to validate data '%s', ignoring..", sensor_data)
      return None

    board_id = sensor_data['board_id']
    sensor_data['board_desc'] = self.boards_map.get(board_id)

    return sensor_data

  def _prepare_action_details(self, sensor_data):
    if not sensor_data:
      return None

    sensor_type = sensor_data.get('sensor_type')
    actions_details = self.sensors_map.get(sensor_type)

    if not actions_details or 'actions' not in actions_details:
      LOG.debug("Missing sensor_map for sensor_type '%s'", sensor_type)
      return None

    for index, action_details in enumerate(actions_details['actions']):

      action_details = ActionDetailsAdapter(action_details)
      action_details.build_defaults(index)

      if not utils.validate_action_details(action_details):
        LOG.warning("Fail to validate data '%s', ignoring..", action_details)
        return None
      else:
        actions_details['actions'][index] = action_details

    return actions_details

  def _action_execute(self, data, actions, action_config):
    result = 0

    for a in actions:
      LOG.debug("Action execute '%s'", a)

      action_name = a['name']
      action_func = ACTIONS_MAPPING.get(action_name)
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

  def _action_helper(self, data, actions_details, action_config=None):

    for action_details in actions_details['actions']:
      LOG.debug("Action helper '%s' '%s'", data, action_details)

      self.action_status.build_defaults(data['board_id'],
              action_details['index'],
              data['sensor_type'])
      self.action_status.clean_failed(data['board_id'],
              action_details['index'],
              data['sensor_type'],
              action_details['fail_interval'])

      if not eval(action_details['threshold'])(data['sensor_data']):
        continue

      try:
        data['message'] = action_details['message_template'].format(**data)
      except (KeyError) as e:
        LOG.error("Fail to format message '%s' with data '%s' missing key '%s'", action_details['message_template'], data, e)
        continue

      if action_details.should_check_if_armed(data['board_id']) and not self.status.get('armed'):
        continue

      if not self.action_status.check_failed_count(data['board_id'],
              action_details['index'],
              data['sensor_type'],
              action_details['fail_count']):
        continue

      if not self.action_status.check_last_action(data['board_id'],
              action_details['index'],
              data['sensor_type'],
              action_details['action_interval']):
        continue

      if self._action_execute(data,
              action_details['action'],
              action_config):
        self.action_status.update_last_action(data['board_id'], action_details['index'], data['sensor_type'])

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.publish_status()
    while True:
      self.enabled.wait()
      try:
        priority, sensor_data, sensor_config = self.action_queue.get(True, 5)
      except (Queue.Empty) as e:
        continue

      LOG.debug("Got sensor_data '%s' with priority '%d'", sensor_data, priority)

      self._action_helper(sensor_data, sensor_config, self.action_config)


LOG = logging.getLogger(__name__)
ACTIONS_MAPPING = utils.load_actions()

def main():
  parser = utils.create_arg_parser('Moteino gateway')
  parser.add_argument('--create-db', required=False, help='Crate mgw database. CAUTION: IT WILL REMOVE OLD DATA', action="store_true")
  parser.add_argument('--sync-db-desc', required=False, help='Sync boards description', action="store_true")
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  sensors_map = utils.load_config(args.dir + '/sensors.config.json')
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

  mgw = MgwThread(
    db_string=conf['db_string'],
    boards_map=boards_map,
    sensors_map=sensors_map,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'])

  mgw.start()


if __name__ == "__main__":
  main()
