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

class SensorActionAdapter(dict):
  """Adapter for sensor action from SensorConfig
  """
  def __init__(self, *args, **kwargs):
    super(SensorActionAdapter, self).__init__(*args, **kwargs)
    self_as_str = json.dumps(self)
    self['id'] = hashlib.md5(self_as_str).hexdigest()

  def action_for_board(self, board_id):
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
    self.setdefault(id_hex, {'board_id': board_id,
      'sensor_type': sensor_type
    })
    self[id_hex].setdefault(sensor_config_id, {'last_action': 0,
      'last_fail': []
    })

  def clean_failed(self, id_hex, sensor_config_id, fail_interval):
    now = int(time.time())
    self[id_hex][sensor_config_id]['last_fail'] = \
      [i for i in self[id_hex][sensor_config_id]['last_fail'] if now - i < fail_interval]

  def check_failed_count(self, id_hex, sensor_config_id, fail_count):
    now = int(time.time())
    failed = self[id_hex][sensor_config_id]['last_fail']
    if len(failed) <= fail_count - 1:
      self[id_hex][sensor_config_id]['last_fail'].append(now)
      return False
    return True

  def check_last_action(self, id_hex, sensor_config_id, action_interval):
    now = int(time.time())
    last_action = self[id_hex][sensor_config_id]['last_action']
    if now - last_action <= action_interval:
      return False
    return True

  def update_last_action(self, id_hex, sensor_config_id):
    now = int(time.time())
    self[id_hex][sensor_config_id]['last_action'] = now


class Mgw(mqtt.Mqtt):
  def __init__(self, db_string, sensors_map_file, action_config, mqtt_config):
    super(Mgw, self).__init__()
    self.name = 'mgw'
    self.enabled = Event()
    self.enabled.set()
    self.status = {'mgw': 1, 'armed': 1}
    self.action_status = ActionStatusAdapter()
    self.db = database.connect(db_string)
    self.action_config = action_config
    self.mqtt_config = mqtt_config
    self.action_queue = Queue.PriorityQueue()

    signal.signal(signal.SIGHUP, self._handle_signal)
    signal.signal(signal.SIGUSR1, self._handle_signal)

    self.sensors_map_file = sensors_map_file
    self._validate_sensors_map(self.sensors_map_file)

    self._get_boards(self.db)

    self.start_mqtt()

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
      sensor_config = sensors_map[sensor_type]
      validation_result, sensor_config = utils.validate_sensor_config(sensor_config)

      if validation_result:
        for idx, action in enumerate(sensor_config['actions']):
          sensor_config['actions'][idx] = SensorActionAdapter(action)
        self.sensors_map[sensor_type] = sensor_config

  def _get_boards(self, db):
    boards = database.get_boards(db)
    self.boards_map = dict((board.board_id, board.board_desc) for board in boards)

  def _on_message(self, client, userdata, msg):
    sensor_data, sensor_config = self._prepare_data(msg)

    if not sensor_data or not sensor_config:
      return

    priority = sensor_config['priority']

    self.action_queue.put((priority, sensor_data, sensor_config))

  def _prepare_data(self, mqtt_msg):
    sensor_data = utils.prepare_sensor_data_mqtt(mqtt_msg)
    sensor_config = self._prepare_sensor_config(sensor_data)

    if sensor_data:
      board_id = sensor_data['board_id']
      sensor_data['board_desc'] = self.boards_map.get(board_id)

    return sensor_data, sensor_config

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

  def _get_value_count(self, value_count=None, board_ids=None, sensor_type=None):
    metrics = []
    if value_count:
      if value_count['type'] == 'Metric':
        metrics = database.get_metrics(self.db,
                board_ids=board_ids,
                sensor_type=sensor_type,
                last_available=value_count['count'])

      elif value_count['type'] == 'LastMetric':
        metrics = database.get_last_metrics(self.db,
                board_ids=board_ids,
                sensor_type=sensor_type)

    return metrics

  def _action_helper(self, sensor_data, sensor_config, action_config=None):

    LOG.debug("Action helper '%s' '%s'", sensor_data, sensor_config['actions'])
    for sensor_action in sensor_config['actions']:

      action_status_id = sensor_data['board_id'] + sensor_data['sensor_type']
      action_status_id_hex = hashlib.md5(action_status_id).hexdigest()

      self.action_status.build_defaults(action_status_id_hex,
              sensor_action['id'],
              sensor_data['board_id'],
              sensor_data['sensor_type'])
      self.action_status.clean_failed(action_status_id_hex,
              sensor_action['id'],
              sensor_action['fail_interval'])

      #Check if config is for given board
      if not sensor_action.action_for_board(sensor_data['board_id']):
        continue

      #Transform sensor_data
      transform_threshold = sensor_action.get('transform')
      if transform_threshold:
        sensor_data['sensor_data'] = utils.eval_helper(transform_threshold,
                sensor_data['sensor_data'])

      #Format message
      try:
        sensor_data['message'] = sensor_action['message_template'].format(**sensor_data)
      except (KeyError, ValueError) as e:
        LOG.error("Fail to format message '%s' with data '%s'", sensor_action['message_template'], sensor_data)
        continue

      #Get historical metrics if needed
      metrics = self._get_value_count(sensor_action['value_count'],
              sensor_data['board_id'],
              sensor_data['sensor_type'])

      #Check threshold function
      threshold_result = utils.eval_helper(sensor_action['threshold'],
              sensor_data['sensor_data'],
              metrics)

      if not threshold_result:
        continue

      #Check status threshold function
      check_status_result = True
      for check_status in sensor_action['check_status']:
        check_status_result = utils.eval_helper(check_status['threshold'],
                self.status.get(check_status['name']))
        if not check_status_result:
          break

      if not check_status_result:
        continue

      #Check metrics threshold function
      check_metric_result = True
      for check_metric in sensor_action['check_metric']:
        metrics = self._get_value_count(check_metric['value_count'],
                check_metric['board_ids'],
                check_metric['sensor_type'])

        check_metric_result = utils.eval_helper(check_metric['threshold'],
                metrics)

        if not check_metric_result:
          break

      if not check_metric_result:
        continue

      #Check failed count
      if not self.action_status.check_failed_count(action_status_id_hex,
              sensor_action['id'],
              sensor_action['fail_count']):
        continue

      #Check last action time
      if not self.action_status.check_last_action(action_status_id_hex,
              sensor_action['id'],
              sensor_action['action_interval']):
        continue


      LOG.info("Action execute for data '%s'", sensor_data)
      if self._action_execute(sensor_data,
              sensor_action['action'],
              action_config,
              sensor_action['action_config']):
        self.action_status.update_last_action(action_status_id_hex, sensor_action['id'])

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
  parser = utils.create_arg_parser('Moteino executor')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')
  sensors_map_file = args.dir + '/sensors.config.json'

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  mgw = Mgw(
    db_string=conf['db_string'],
    sensors_map_file=sensors_map_file,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'])

  mgw.run()


if __name__ == "__main__":
  main()
