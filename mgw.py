#!/usr/local/bin/python
import serial
import time
import json
import sqlite3
import threading
import random
import logging
import sys
import os
import daemonocle
import socket
import re

def notify(logger, data):
  logger.info('Performing notify action for data {}'.format(data))
  return True

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config

def connect_db(db_file):
  db = sqlite3.connect(db_file)
  return db

def create_db(db_file, create_sensor_table=False):
  board_map = load_config('boards.config.json')
  db = connect_db(db_file)
  db.execute("DROP TABLE IF EXISTS board_desc");
  db.execute('''CREATE TABLE board_desc(board_id TEXT PRIMARY KEY, board_desc TEXT)''');

  for key in board_map:
    db.execute("INSERT INTO board_desc(board_id, board_desc) VALUES(?, ?)",
      (key, board_map[key]))
  db.commit()

  if (create_sensor_table):
    db.execute("DROP TABLE IF EXISTS sensors")
    db.execute('''CREATE TABLE sensors (id INTEGER PRIMARY KEY AUTOINCREMENT, board_id TEXT, sensor_type TEXT,
      last_update TIMESTAMP DEFAULT (STRFTIME('%s', 'now')), data TEXT DEFAULT NULL)''')

def create_logger(level, log_file, daemon):
  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

  if daemon:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)

  return logger

class mgmt_Thread(threading.Thread):
  def __init__(self, conf, daemon):
    threading.Thread.__init__(self)
    threading.current_thread().name = 'mgmt'
    self._daemon = daemon
    self.daemon = True
    self.socket = conf['mgmt_socket']
    self.serial = serial.Serial(conf['serial']['device'], conf['serial']['speed'], timeout=conf['serial']['timeout'])
    self.logger = create_logger(conf['logging']['level'], conf['logging']['file'], conf['daemon'])

    self.msd = failure_Thread('msd', self.logger, conf['loop_sleep'],
      conf['db_file'], conf['msd']['cache_time'],
      conf['msd']['failure_value'],
      conf['msd']['failure_query']) #Missing sensor detector
    self.mgw = mgw_Thread(self.logger, self.serial, conf['loop_sleep'], conf['gateway_ping_time'], conf['db_file'])

  def run(self):
    self.logger.info('Starting')

    self.msd.start()
    self.mgw.start()

    if os.path.exists(self.socket):
      os.remove(self.socket)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(self.socket)
    server.listen(1)
    while True:
      conn, addr = server.accept()
      data = conn.recv(1024)
      if data:
        try:
          data = json.loads(data)
        except (ValueError) as e:
          self.logger.warning('Got exception \'{}\' while reading from socket'.format(e))
          continue
        if 'action' in data:
          if data['action'] == 'status':
            conn.send(json.dumps(STATUS))
          elif data['action'] == 'send' and 'data' in data:
            try:
              r_cmd = str(data['data']['nodeid'])+":"+str(data['data']['cmd'])
              self.serial.write(r_cmd)
            except (IOError, ValueError, serial.serialutil.SerialException) as e:
              self.logger.error('Fail to send command ({}) to remote node'.format(r_cmd))
          elif data['action'] == 'set' and 'data' in data:
            for key in data['data']:
              self.logger.warning('Setting {} to {}'.format(key, data['data'][key]))
              STATUS[key] = data['data'][key]
              if key == 'mgw_enabled':
                self.mgw.enabled.set() if data['data'][key] else self.mgw.enabled.clear()
              elif key == 'msd_enabled':
                self.msd.enabled.set() if data['data'][key] else self.msd.enabled.clear()

      conn.close()

class failure_Thread(threading.Thread):
  def __init__(self, name, logger, loop_sleep, db_file, cache_time, failure_value, failure_query):
    threading.Thread.__init__(self)
    self.name = name
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS[name+'_enabled']:
      self.enabled.set()
    self.logger = logger
    self.loop_sleep = loop_sleep
    self.db_file = db_file
    self.cache_time = cache_time
    self.failure_value = failure_value
    self.failure_query = failure_query
    self.failed = {}

  def handle_failed(failed_node, failed_value):
    now = int(time.time())
    if self.name == 'msd':
      self.logger.warning('No update from board {} since {} seconds'.format(failed_node,
          now - failed_value))

  def run(self):
    self.logger.info('Starting')
    self.db = connect_db(self.db_file)
    while True:
      self.enabled.wait()
      now = int(time.time())

      for failed_node, failed_value in self.db.execute(self.failure_query, (self.failure_value, )):
        if failed_node in self.failed:
          if now - self.failed[failed_node] > self.cache_time:
            self.logger.debug('Removing failed node {} from cache'.format(failed_node))
            del self.failed[failed_node]
            self.handle_failed(failed_node, failed_value)
        else:
          self.failed[failed_node] = now
          self.handle_failed(failed_node, failed_value)

      time.sleep(self.loop_sleep)

class mgw_Thread(threading.Thread):
  def __init__(self, logger, serial, loop_sleep, gateway_ping_time, db_file):
    threading.Thread.__init__(self)
    self.name = 'mgw'
    self.daemon = True
    self.enabled = threading.Event()
    if STATUS["msd_enabled"]:
      self.enabled.set()
    self.logger = logger
    self.serial = serial
    self.loop_sleep = loop_sleep
    self.gateway_ping_time = gateway_ping_time
    self.db_file = db_file
    self.s_type_map = load_config('sensors.config.json')
    self.action_status = {}

  def ping_gateway(self):
    try:
      self.serial.write('1:1')
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      logger.error('Failed to get measure from gateway: {}'.format(e))
    time.sleep(1)
    return int(time.time())

  def action_helper(self, data, action, check_if_armed, action_interval, threshold):
    self.logger.debug('Action helper for data: {}'.format(data))
    now = int(time.time())
    if (check_if_armed) and (not STATUS['armed']):
      self.logger.info('Check if armed required, but status is not armed')
      return

    self.action_status.setdefault(data['board_id'], {})
    self.action_status[data['board_id']].setdefault(data['sensor_type'], 0)

    if (now - self.action_status[data['board_id']][data['sensor_type']] > action_interval):
      if (threshold(data['sensor_data']) and action(self.logger, data)):
        self.action_status[data['board_id']][data['sensor_type']] = now

  def run(self):
    self.logger.info('Starting')
    self.db = connect_db(self.db_file)

    #[ID][metric:value] / [10][voltage:3.3]
    re_data = re.compile('\[(\d+)\]\[(.+):(.+)\]')

    last_gw_ping = 0
    data = {}

    while True:
      self.enabled.wait()
      try:
        s_data = self.serial.readline().strip()
        m = re_data.match(s_data)
        #{"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
        data['board_id'], data['sensor_type'], data['sensor_data'] = [m.group(i) for i in range(1, 4)]
      except (IOError, ValueError, serial.serialutil.SerialException) as e:
        self.logger.error('Got exception \'{}\' while reading from serial'.format(e))
        self.serial.close()
        time.sleep(self.loop_sleep)
        try:
          self.serial.open()
        except (OSError) as e:
          self.logger.warning('Failed to open serial')
        continue
      except (AttributeError) as e:
        if len(s_data) > 0:
          self.logger.debug('> {}'.format(s_data))
        continue
      finally:
        if (int(time.time()) - last_gw_ping >= self.gateway_ping_time):
          last_gw_ping = self.ping_gateway()

      self.logger.debug('Got data from serial {}'.format(data))

      try:
        self.db.execute("INSERT INTO sensors(board_id, sensor_type, data) VALUES(?, ?, ?)",
                (data['board_id'], data['sensor_type'], data['sensor_data']))
        self.db.commit()
      except (sqlite3.IntegrityError) as e:
        self.logger.error('Integrity error {}'.format(e))
      except (sqlite3.OperationalError) as e:
        time.sleep(random.randint(1,5))
        try:
          self.db.commit()
        except (sqlite3.OperationalError) as e:
          self.logger.error('Failed to commit data to DB');

      try:
        action_details = self.s_type_map[data['sensor_type']]
      except (KeyError) as e:
        self.logger.debug('Missing s_type_map for sensor_type {}'.format(data['sensor_type']))
        continue

      self.action_helper(data,
        eval(action_details['action']),
        action_details.get('check_if_armed', 1),
        action_details.get('action_interval', 0),
        eval(action_details.get('threshold', 'lambda x: True')))

STATUS = {
  "armed": 1,
  "msd_enabled": 1,
  "mgw_enabled": 1,
}

if __name__ == "__main__":
  conf = load_config('global.config.json')
  daemon = daemonocle.Daemon(pidfile=conf['pid_file'], detach=conf['daemon'])
  mgmt = mgmt_Thread(conf=conf, daemon=daemon)

  if len(sys.argv) < 2:
    print('Usage: start|stop|restart|status')
    sys.exit(1)

  daemon.worker = mgmt.run
  daemon.do_action(sys.argv[1])
