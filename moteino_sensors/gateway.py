#!/usr/bin/env python
import argparse
import logging
import random
import re
import sqlite3
import sys
import threading
import time
import Queue
import paho.mqtt.client as paho

import serial

from moteino_sensors import database
from moteino_sensors import utils
from moteino_sensors import mqtt


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


class ExcThread(mqtt.MqttThread):

  def __init__(self, boards_map, sensors_map, action_config, mqtt_config):
    super(ExcThread, self).__init__()
    self.name = 'exc'
    self.daemon = True
    self.action_status = {}
    self.boards_map = boards_map
    self.sensors_map = sensors_map
    self.action_config = action_config
    self.mqtt_config = mqtt_config
    self.action_queue = Queue.Queue()

    self.start_mqtt()

    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name], self.on_message)

  def on_message(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)
    self.action_queue.put(sensor_data)

  def action_execute(self, data, actions, action_config):
    result = 0

    for a in actions:
      LOG.debug("Action execute '%s'", a)

      action_name = a['name']
      action_func = utils.ACTIONS_MAPPING.get(action_name)
      conf = action_config.get(action_name)

      if not action_func:
        LOG.warning('Unknown action %s', action_name)
        continue

      if not action_func(data, conf):
        LOG.error("Fail to execute action '%s'", action_name)
        failback_actions = a.get('failback')
        if failback_actions:
          LOG.debug("Failback '%s'", failback_actions)
          result += self.action_execute(data, failback_actions, action_config)
      else:
        result += 1

    return result

  def action_helper(self, data, action_details, action_config=None):
    if not action_details or not action_details.get('action'):
      LOG.debug("Missing sensor_map/action for sensor_type '%s'", data['sensor_type'])
      return

    action_details.setdefault('check_if_armed', {'default': True})
    action_details['check_if_armed'].setdefault('except', [])
    action_details.setdefault('action_interval', 0)
    action_details.setdefault('threshold', 'lambda x: True')
    action_details.setdefault('fail_count', 0)
    action_details.setdefault('fail_interval', 600)
    action_details.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')

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

    if self.action_execute(data, action_details['action'], action_config):
      self.action_status[data['board_id']][data['sensor_type']]['last_action'] = now

  def run(self):
    LOG.info('Starting')
    while True:
      self.mqtt.loop()
      try:
        sensor_data = self.action_queue.get(True, 5)
      except (Queue.Empty) as e:
        continue

      #Todo: Check if sensor_data have proper format
      sensor_type = sensor_data['sensor_type']
      sensor_config = self.sensors_map.get(sensor_type)

      board_id = str(sensor_data['board_id'])
      sensor_data['board_desc'] = self.boards_map.get(board_id)

      self.action_helper(sensor_data, sensor_config, self.action_config)


class MgwThread(mqtt.MqttThread):

  # [ID][metric:value] / [10][voltage:3.3]
  _re_sensor_data = re.compile(
    '\[(?P<board_id>\d+)\]\[(?P<sensor_type>.+):(?P<sensor_data>.+)\]')
  status = {
    'mgw': 1,
    'msd': 1,
    'armed': 1,
    'fence': 1
  }

  def __init__(self, serial, gateway_ping_time, db_file, mqtt_config):
    super(MgwThread, self).__init__()
    self.name = 'mgw'
    self.enabled = threading.Event()
    self.enabled.set()
    self.serial = serial
    self.last_gw_ping = 0
    self.gateway_ping_time = gateway_ping_time
    self.db_file = db_file
    self.mqtt_config = mqtt_config
    self.start_mqtt()
    self.sensor_queue = Queue.Queue()


    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/metric', self.on_message_metric)
    self.mqtt.message_callback_add(self.mqtt_config['topic'][self.name]+'/serial', self.on_message_serial)

  def on_message_metric(self, client, userdata, msg):
    sensor_data = utils.load_json(msg.payload)
    self.sensor_queue.put(sensor_data)

  def on_message_serial(self, client, userdata, msg):
    data = utils.load_json(msg.payload)

    try:
      r_cmd = "{nodeid}:{cmd}".format(**data['data'])
      self.serial.write(r_cmd)
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%s' in mgmt thread", e)

  def ping_gateway(self):
    try:
      self.serial.write('1:1')
      time.sleep(1)
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%' in ping_gateway", e)
    else:
      self.last_gw_ping = int(time.time())

  def _read_sensors_data(self):
    data = {}
    try:
      s_data = self.serial.readline().strip()
      m = self._re_sensor_data.match(s_data)
      # {"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
      data = m.groupdict()
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      LOG.error("Got exception '%' in mgw thread", e)
      self.serial.close()
      time.sleep(5)
      try:
        self.serial.open()
      except (OSError) as e:
        LOG.warning('Failed to open serial')
    except (AttributeError) as e:
      if len(s_data) > 0:
        LOG.debug('> %s', s_data)
    finally:
      if (int(time.time()) - self.last_gw_ping >= self.gateway_ping_time):
        self.ping_gateway()

    return data

  def _save_sensors_data(self, data):
    try:
      self.db.execute(
        "INSERT INTO metrics(board_id, sensor_type, data) VALUES(?, ?, ?)",
        (data['board_id'], data['sensor_type'], data['sensor_data'])
      )
      self.db.commit()
    except (sqlite3.IntegrityError) as e:
      LOG.error("Got exception '%' in mgw thread", e)
    except (sqlite3.OperationalError) as e:
      time.sleep(1 + random.random())
      try:
        self.db.commit()
      except (sqlite3.OperationalError) as e:
        LOG.error("Got exception '%' in mgw thread", e)

  def run(self):
    LOG.info('Starting')
    self.db = database.connect(self.db_file)
    self.mqtt.loop_start()
    self.mqtt._thread.setName(self.name+'-mqtt')
    mqtt.publish(self.mqtt, self.mqtt_config['topic']['mgmt']+'/status', self.status, retain=True)

    while True:
      self.enabled.wait()

      sensor_data = self._read_sensors_data()
      if not sensor_data:
        continue

      #todo: rewrite reading->queue.put->queue.get
      self.sensor_queue.put(sensor_data)
      try:
        sensor_data = self.sensor_queue.get(True, 5)
      except (Queue.Empty) as e:
        continue

      LOG.debug("Got data from serial '%s'", sensor_data)

      self._save_sensors_data(sensor_data)

      mqtt.publish(self.mqtt, self.mqtt_config['topic']['exc'], sensor_data)


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

  ser = serial.Serial(
    conf['serial']['device'],
    conf['serial']['speed'],
    timeout=conf['serial']['timeout']
  )
  mgw = MgwThread(
    serial=ser,
    gateway_ping_time=conf['gateway_ping_time'],
    db_file=conf['db_file'],
    mqtt_config=conf['mqtt'])

  exc = ExcThread(
    boards_map=boards_map,
    sensors_map=sensors_map,
    action_config=conf['action_config'],
    mqtt_config=conf['mqtt'])

  mgw.start()
  exc.start()


if __name__ == "__main__":
  main()
