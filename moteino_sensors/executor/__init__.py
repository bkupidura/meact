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

from sqlalchemy.exc import OperationalError

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils
from moteino_sensors.executor import actions

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


class Executor(mqtt.Mqtt):
  def __init__(self, db_string, sensors_map_file, action_config, mqtt_config):
    super(Executor, self).__init__()
    self.name = 'executor'
    self.enabled = Event()
    self.enabled.set()
    self.status = {'executor': 1, 'armed': 1}
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

  def _on_mgmt_status(self, client, userdata, msg):
    super(Executor, self)._on_mgmt_status(client, userdata, msg)

    status_topic = self.mqtt_config['topic'].get('mgmt/status')
    metric_topic = self.mqtt_config['topic'].get('executor/metric')

    if not status_topic or not metric_topic:
      return

    status_name = msg.topic[len(status_topic)+1:]

    sensor_data = {
      'sensor_type': status_name,
      'board_id': self.name,
      'sensor_data': msg.payload
    }
    self.publish_metric(metric_topic, sensor_data)

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

  def _check_status(self, sensor_check_status):
    check_status_result = True
    for check_status in sensor_check_status:
      _, check_status_result = utils.treshold_helper(check_status['threshold'],
              self.status.get(check_status['name']))
      if not check_status_result:
        break

    return check_status_result

  def _check_metric(self, sensor_check_metric, sensor_data):
    check_metric_result = True
    for check_metric in sensor_check_metric:
      board_ids = check_metric.get('board_ids', [])
      board_ids = map(lambda x: x.format(**sensor_data), board_ids)

      try:
        metrics = self._get_value_count(check_metric['value_count'],
                board_ids,
	        check_metric.get('sensor_type'),
	        check_metric.get('start_offset'),
	        check_metric.get('end_offset'))
      except OperationalError as e:
        LOG.error("Fail to get metrics '%s'", e)
        check_metric_result = False
        break

      _, check_metric_result = utils.treshold_helper(check_metric['threshold'],
              metrics)

      if not check_metric_result:
        break

    return check_metric_result

  def _check_action_interval(self, sensor_data, sensor_action_id, action_interval):
    try:
      last_actions = database.get_action(self.db, sensor_data['board_id'],
              sensor_data['sensor_type'], sensor_action_id, 1)
    except OperationalError as e:
      last_actions = None
      LOG.error("Fail to get action '%s'", e)

    if not last_actions:
      last_action = 0
    else:
      last_action = last_actions[0].last_update

    return utils.time_offset(-last_action) > action_interval

  def _get_value_count(self, value_count, board_ids=None, sensor_type=None, start_offset=None, end_offset=None):
    db_params = {
      'db': self.db,
      'board_ids': board_ids,
      'sensor_type': sensor_type,
      'start': utils.time_offset(start_offset),
      'end': utils.time_offset(end_offset)
    }

    if value_count['type'] == 'Metric':
      db_params['last_available'] = value_count['count']
      metrics = database.get_metrics(**db_params)
    elif value_count['type'] == 'LastMetric':
      metrics = database.get_last_metrics(**db_params)
    else:
      metrics = []

    return metrics

  def _action_helper(self, sensor_data, sensor_config, action_config=None):

    LOG.debug("Action helper '%s' '%s'", sensor_data, sensor_config['actions'])
    for sensor_action in sensor_config['actions']:

      #Check if config is for given board
      if not sensor_action.action_for_board(sensor_data['board_id']):
        continue

      #Check threshold function
      sensor_data['sensor_data'], threshold_result = utils.treshold_helper(sensor_action['threshold'],
              sensor_data['sensor_data'])

      if not threshold_result:
        continue

      #Format message
      try:
        sensor_data['message'] = sensor_action['message_template'].format(**sensor_data)
      except (KeyError, ValueError) as e:
        LOG.error("Fail to format message '%s' with data '%s'", sensor_action['message_template'], sensor_data)
        continue

      #Check status threshold function
      if not self._check_status(sensor_action['check_status']):
        continue

      #Check metrics threshold function
      if not self._check_metric(sensor_action['check_metric'], sensor_data):
        continue

      #Check last action time
      if not self._check_action_interval(sensor_data, sensor_action['id'],
              sensor_action['action_interval']):
        continue

      LOG.info("Action execute for data '%s'", sensor_data)
      if self._action_execute(sensor_data,
              sensor_action['action'],
              action_config,
              sensor_action['action_config']):
        try:
          database.insert_action(self.db, sensor_data['board_id'],
                  sensor_data['sensor_type'], sensor_action['id'])
        except OperationalError as e:
          LOG.error("Fail to save action '%s'", e)

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
ACTIONS_MAPPING = utils.load_mapping(actions)

def main():
  parser = utils.create_arg_parser('Moteino executor')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.yaml')
  conf = conf.get('executor', {})
  sensors_map_file = args.dir + '/sensors.yaml'

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  executor = Executor(
    db_string=conf['db_string'],
    sensors_map_file=sensors_map_file,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'])

  executor.run()


if __name__ == "__main__":
  main()
