#!/usr/bin/env python
from multiprocessing import Process
from threading import Event
import Queue
import hashlib
import json
import logging
import random
import signal
import time

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils


class SensorConfigAdapter(dict):
  """Adapter for sensor config

  Provides helpers and functions that allows
  to easily work on sensor config
  """
  def build_defaults(self):
    self.setdefault('check_if_armed', {'default': False})
    self.setdefault('action_interval', 0)
    self.setdefault('threshold', 'lambda x: True')
    self.setdefault('fail_count', 0)
    self.setdefault('fail_interval', 600)
    self.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')
    self.setdefault('action_config', {})
    self.setdefault('board_ids', [])
    self.setdefault('value_count', 0)

    self['check_if_armed'].setdefault('except', [])

    self_as_str = json.dumps(self)
    self['id'] = hashlib.md5(self_as_str).hexdigest()

  def should_check_if_armed(self, board_id):
    """Should action be checked for given board?"""
    return (
      self['check_if_armed']['default']
      ^
      (board_id in self['check_if_armed']['except'])
    )

  def config_for_board(self, board_id):
    if self['board_ids'] and board_id in self['board_ids']:
      return True
    elif not self['board_ids']:
      return True
    return False


class ActionStatusAdapter(dict):
  """Adapter for action status

  Provider helpers and functions that allows
  to easily work with action status
  """
  def build_defaults(self, id_hex, sensor_config_id, board_id, sensor_type):
    self.setdefault(id_hex, {'last_action': 0,
        'last_fail': [],
        'last_value': [],
        'sensor_config_id': sensor_config_id,
        'board_id': board_id,
        'sensor_type': sensor_type})

  def clean_failed(self, id_hex, fail_interval):
    now = int(time.time())
    self[id_hex]['last_fail'] = \
      [i for i in self[id_hex]['last_fail'] if now - i < fail_interval]

  def check_failed_count(self, id_hex, fail_count):
    now = int(time.time())
    failed = self[id_hex]['last_fail']
    if len(failed) <= fail_count - 1:
      self[id_hex]['last_fail'].append(now)
      return False
    return True

  def check_last_action(self, id_hex, action_interval):
    now = int(time.time())
    last_action = self[id_hex]['last_action']
    if now - last_action <= action_interval:
      return False
    return True

  def update_last_action(self, id_hex):
    now = int(time.time())
    self[id_hex]['last_action'] = now

  def update_values(self, id_hex, value_count, value):
    if value_count > 0:
      self[id_hex]['last_value'].append(value)
      while len(self[id_hex]['last_value']) > value_count:
        self[id_hex]['last_value'].pop(0)

  def get_values(self, id_hex):
    return self[id_hex]['last_value']


class Mgw(mqtt.Mqtt):
  def __init__(self, db_string, sensors_map_file, action_config, mqtt_config, status):
    super(Mgw, self).__init__()
    self.name = 'mgw'
    self.enabled = Event()
    self.enabled.set()
    self.action_status = ActionStatusAdapter()
    self.db = database.connect(db_string)
    self.action_config = action_config
    self.mqtt_config = mqtt_config
    self.status = status
    self.action_queue = Queue.PriorityQueue()

    signal.signal(signal.SIGHUP, self._handle_signal)
    signal.signal(signal.SIGUSR1, self._handle_signal)

    self.sensors_map_file = sensors_map_file
    self._validate_sensors_map(self.sensors_map_file)

    self._get_boards(self.db)

    self.start_mqtt()

    self.mqtt.message_callback_add(self.mqtt_config['topic']['dbsm'], self._on_message_action)
    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/action', self._on_message_action)

  def _handle_signal(self, signum, stack):
    if signum == signal.SIGHUP:
      LOG.info('Refreshing boards and sensors map')
      self._get_boards(self.db)
      self._validate_sensors_map(self.sensors_map_file)
    elif signum == signal.SIGUSR1:
      LOG.info("Action status: %s", self.action_status)
      LOG.info("Action config: %s", self.action_config)
      LOG.info("Sensors map: %s", self.sensors_map)
      LOG.info("Boards map: %s", self.boards_map)


  def _validate_sensors_map(self, sensors_map_file):
    sensors_map = utils.load_config(sensors_map_file)
    self.sensors_map = dict()

    for sensor_type in sensors_map:
      sensor_configs = sensors_map[sensor_type]

      if 'actions' not in sensor_configs:
        LOG.warning("No actions defined for '%s', ignoring..", sensor_type)
        continue

      if not 'priority' in sensor_configs or not isinstance(sensor_configs['priority'], int):
        sensor_configs['priority'] = 500

      actions = list()
      for sensor_config in sensor_configs['actions']:
        sensor_config = SensorConfigAdapter(sensor_config)
        sensor_config.build_defaults()

        if not utils.validate_sensor_config(sensor_config):
          LOG.warning("Fail to validate data '%s', ignoring..", sensor_config)
        else:
          actions.append(sensor_config)

      sensor_configs['actions'] = actions
      if len(sensor_configs['actions']):
        self.sensors_map[sensor_type] = sensor_configs

  def _get_boards(self, db):
    boards = database.get_boards(db)
    self.boards_map = dict((board.board_id, board.board_desc) for board in boards)

  def _on_message_action(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)

    sensor_data, sensor_config = self._prepare_data(sensor_data)

    self._put_in_queue(sensor_data, sensor_config)

  def _put_in_queue(self, sensor_data, sensor_config):
    if not sensor_data or not sensor_config:
      return

    priority = sensor_config['priority']

    self.action_queue.put((priority, sensor_data, sensor_config))

  def _prepare_data(self, sensor_data):
    sensor_data = self._prepare_sensor_data(sensor_data)
    sensor_config = self._prepare_sensor_config(sensor_data)

    return sensor_data, sensor_config

  def _prepare_sensor_data(self, sensor_data):
    if not utils.validate_sensor_data(sensor_data):
      LOG.warning("Fail to validate data '%s', ignoring..", sensor_data)
      return None

    board_id = sensor_data['board_id']
    sensor_data['board_desc'] = self.boards_map.get(board_id)

    return sensor_data

  def _prepare_sensor_config(self, sensor_data):
    if not sensor_data:
      return None

    sensor_type = sensor_data.get('sensor_type')
    sensor_configs = self.sensors_map.get(sensor_type)

    if not sensor_configs:
      LOG.debug("Missing sensor_map for sensor_type '%s'", sensor_type)
      return None

    return sensor_configs

  def _action_execute(self, sensor_data, actions, global_action_config, sensor_action_config):
    result = 0

    for action in actions:
      LOG.debug("Action execute '%s'", action)

      action_name = action['name']
      action_func = ACTIONS_MAPPING.get(action_name)

      action_config = global_action_config.get(action_name, {})
      sensor_config = sensor_action_config.get(action_name, {})
      action_config.update(sensor_config)

      if not action_func:
        LOG.warning('Unknown action %s', action_name)
        continue

      p = Process(target=action_func.get('func'), args=(sensor_data, action_config))
      p.start()
      p.join(action_func.get('timeout'))
      if p.is_alive():
        p.terminate()
        status = 255
      else:
        status = p.exitcode

      if status:
        LOG.error("Fail to execute action '%s', exitcode '%d'", action_name, status)
        failback_actions = action.get('failback')
        if failback_actions:
          LOG.debug("Failback '%s'", failback_actions)
          result += self._action_execute(sensor_data, failback_actions, global_action_config, sensor_action_config)
      else:
        result += 1

    return result

  def _action_helper(self, sensor_data, sensor_configs, action_config=None):

    LOG.debug("Action helper '%s' '%s'", sensor_data, sensor_configs['actions'])
    for sensor_config in sensor_configs['actions']:

      action_status_id = sensor_config['id'] + sensor_data['board_id'] + sensor_data['sensor_type']
      action_status_id_hex = hashlib.md5(action_status_id).hexdigest()

      self.action_status.build_defaults(action_status_id_hex,
              sensor_config['id'],
              sensor_data['board_id'],
              sensor_data['sensor_type'])
      self.action_status.clean_failed(action_status_id_hex,
              sensor_config['fail_interval'])

      if not sensor_config.config_for_board(sensor_data['board_id']):
        continue

      threshold_func = eval(sensor_config['threshold'])
      threshold_func_arg_number = threshold_func.func_code.co_argcount
      if threshold_func_arg_number == 1:
        threshold_result = threshold_func(sensor_data['sensor_data'])
      elif threshold_func_arg_number == 2:
        try:
          threshold_result = threshold_func(sensor_data['sensor_data'], self.action_status.get_values(action_status_id_hex))
        except (IndexError):
          LOG.info('Not enough values stored to check threshold')
          threshold_result = False

      self.action_status.update_values(action_status_id_hex, sensor_config['value_count'], sensor_data['sensor_data'])

      if not threshold_result:
        continue

      try:
        sensor_data['message'] = sensor_config['message_template'].format(**sensor_data)
      except (KeyError, ValueError) as e:
        LOG.error("Fail to format message '%s' with data '%s'", sensor_config['message_template'], sensor_data)
        continue

      if sensor_config.should_check_if_armed(sensor_data['board_id']) and not self.status.get('armed'):
        continue

      if not self.action_status.check_failed_count(action_status_id_hex,
              sensor_config['fail_count']):
        continue

      if not self.action_status.check_last_action(action_status_id_hex,
              sensor_config['action_interval']):
        continue

      LOG.info("Action execute for data '%s'", sensor_data)
      if self._action_execute(sensor_data,
              sensor_config['action'],
              action_config,
              sensor_config['action_config']):
        self.action_status.update_last_action(action_status_id_hex)

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
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  sensors_map_file = args.dir + '/sensors.config.json'

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  mgw = Mgw(
    db_string=conf['db_string'],
    sensors_map_file=sensors_map_file,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'],
    status=conf['status'])

  mgw.run()


if __name__ == "__main__":
  main()
