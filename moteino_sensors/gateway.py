#!/usr/bin/env python
import abc
import argparse
import json
import logging
import os
import random
import re
import socket
import sqlite3
import sys
import threading
import time

import serial

from moteino_sensors import database
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


def action_execute(data, actions, action_config):
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
      failback_actions = a.get('failback')
      if failback_actions:
        LOG.debug('Action failed, failback %s', failback_actions)
        result += action_execute(data, failback_actions, action_config)
    else:
      result += 1

  return result


def action_helper(data, action_details, action_config=None):
  action_details.setdefault('check_if_armed', {'default': True})
  action_details['check_if_armed'].setdefault('except', [])
  action_details.setdefault('action_interval', 0)
  action_details.setdefault('threshold', 'lambda x: True')
  action_details.setdefault('fail_count', 0)
  action_details.setdefault('fail_interval', 600)
  action_details.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')

  try:
    data['message'] = action_details['message_template'].format(**data)
  except (KeyError) as e:
    LOG.error("Fail to format message '%s' with data '%s'", action_details['message_template'], data)
    return

  action_details = ActionDetailsAdapter(action_details)

  LOG.debug("Action helper '%s' '%s'", data, action_details)
  now = int(time.time())

  ACTION_STATUS.setdefault(data['board_id'], {})
  ACTION_STATUS[data['board_id']].setdefault(data['sensor_type'], {'last_action': 0, 'last_fail': []})

  ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'] = \
    [i for i in ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'] if now - i < action_details['fail_interval']]

  if action_details.should_check_if_armed(data['board_id']) and not STATUS['armed']:
    return

  if not eval(action_details['threshold'])(data['sensor_data']):
    return

  if len(ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail']) <= action_details['fail_count']-1:
    ACTION_STATUS[data['board_id']][data['sensor_type']]['last_fail'].append(now)
    return

  if (now - ACTION_STATUS[data['board_id']][data['sensor_type']]['last_action'] <= action_details['action_interval']):
    return

  if action_execute(data, action_details['action'], action_config):
    ACTION_STATUS[data['board_id']][data['sensor_type']]['last_action'] = now


class mgmt_Thread(threading.Thread):
  def __init__(self, conf, boards_map, sensors_map):
    super(mgmt_Thread, self).__init__()
    self.name = 'mgmt'

    self.socket = conf['mgmt_socket']
    self.serial = serial.Serial(
      conf['serial']['device'],
      conf['serial']['speed'],
      timeout=conf['serial']['timeout']
    )

    # Missing sensor detector thread
    self.msd = msd_Thread(
      loop_sleep=conf['msd']['loop_sleep'],
      db_file=conf['db_file'],
      query=conf['msd']['query'],
      board_map=boards_map,
      sensor_map=sensors_map,
      action_config=conf['action_config'])

    self.mgw = mgw_Thread(
      serial=self.serial,
      loop_sleep=conf['loop_sleep'],
      gateway_ping_time=conf['gateway_ping_time'],
      db_file=conf['db_file'],
      board_map=boards_map,
      sensor_map=sensors_map,
      action_config=conf['action_config'])

  def handle_action(self, data):
    if 'action' not in data:
      LOG.debug('No action to handle')

    if data['action'] == 'status':
      return STATUS

    if data['action'] == 'send' and 'data' in data:
      try:
        r_cmd = "{nodeid}:{cmd}".format(**data['data'])
        self.serial.write(r_cmd)
      except (IOError, ValueError, serial.serialutil.SerialException) as e:
        LOG.error("Got exception '%s' in mgmt thread", e)

    if data['action'] == 'set' and 'data' in data:
      STATUS.update(data['data'])

      if 'mgw' in data['data']:
        self.mgw.enabled.set() if data['data']['mgw'] else self.mgw.enabled.clear()
      if 'msd' in data['data']:
        self.msd.enabled.set() if data['data']['msd'] else self.msd.enabled.clear()

  def run(self):
    LOG.info('Starting')

    self.msd.start()
    self.mgw.start()

    if os.path.exists(self.socket):
      os.remove(self.socket)

    # TODO(prmtl): write a socket server class that will abstract this?
    self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.server.bind(self.socket)
    self.server.listen(1)

    while True:
      # TODO(prmtl): check if we can do it onece
      conn, addr = self.server.accept()
      data = conn.recv(1024)

      LOG.debug("Got '%s' on mgmt socket", data)

      if not data:
        continue

      try:
        data = json.loads(data)
      except (ValueError) as e:
        LOG.warning("Cannot decode recieved data in mgmt thread: %s", e)
        continue

      response = self.handle_action(data)
      if response:
        conn.send(json.dumps(response))

      conn.close()


class DBQueryThread(threading.Thread):
  __metaclass__ = abc.ABCMeta

  name = None

  def __init__(self, loop_sleep, db_file, query,
          sensor_map, board_map, action_config):
    super(DBQueryThread, self).__init__()
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS[self.name]:
      self.enabled.set()
    self.loop_sleep = loop_sleep
    self.db_file = db_file
    self.query = query
    self.sensor_map = sensor_map
    self.board_map = board_map
    self.action_config = action_config
    self.failed = {}

  def run(self):
    LOG.info('Starting')
    self.db = database.connect(self.db_file)
    while True:
      self.enabled.wait()

      result = self.db.execute(self.query)
      self.handle_query_result(result)

      time.sleep(self.loop_sleep)

  def handle_query_result(self, query_result):
      for board_id, value in query_result:
        self.handle_result(board_id, value)

  @abc.abstractmethod
  def handle_result(self, board_id, value):
    pass


class msd_Thread(DBQueryThread):

  name = 'msd'

  def handle_result(self, board_id, value):
    now = int(time.time())
    data = {'board_id': board_id,
            'board_desc': self.board_map.get(board_id),
            'sensor_data': now - value,
            'sensor_type': self.name}

    sensor_config = self.sensor_map.get(self.name)
    if not sensor_config or not sensor_config.get('action'):
      LOG.error("Missing sensor_map/action for sensor_type '%s'", sensor_type)
      return

    action_helper(data, sensor_config, self.action_config)


class mgw_Thread(threading.Thread):

  # [ID][metric:value] / [10][voltage:3.3]
  _re_sensor_data = re.compile(
    '\[(?P<board_id>\d+)\]\[(?P<sensor_type>.+):(?P<sensor_data>.+)\]')

  def __init__(self, serial, loop_sleep, gateway_ping_time,
          db_file, board_map, sensor_map, action_config):
    super(mgw_Thread, self).__init__()
    self.name = 'mgw'
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS[self.name]:
      self.enabled.set()
    self.serial = serial
    self.loop_sleep = loop_sleep
    self.last_gw_ping = 0
    self.gateway_ping_time = gateway_ping_time
    self.db_file = db_file
    self.sensor_map = sensor_map
    self.board_map = board_map
    self.action_config = action_config

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
      time.sleep(self.loop_sleep)
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

    while True:
      self.enabled.wait()

      sensor_data = self._read_sensors_data()
      if not sensor_data:
        continue

      LOG.debug("Got data from serial '%s'", sensor_data)

      self._save_sensors_data(sensor_data)

      sensor_type = sensor_data['sensor_type']

      sensor_config = self.sensor_map.get(sensor_type)
      if not sensor_config or not sensor_config.get('action'):
        LOG.debug("Missing sensor_map/action for sensor_type '%s'", sensor_type)
        continue

      board_id = str(sensor_data['board_id'])
      sensor_data['board_desc'] = self.board_map.get(board_id)
      action_helper(sensor_data, sensor_config, self.action_config)


STATUS = {
  "armed": 1,
  "msd": 1,
  "mgw": 1,
  "fence": 1,
}

ACTION_STATUS = {}

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

  mgmt = mgmt_Thread(
    conf=conf,
    boards_map=boards_map,
    sensors_map=sensors_map,
  )
  mgmt.start()


if __name__ == "__main__":
  main()
