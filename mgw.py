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
import random

def notify(data):
  logger.info('Performing action notify for board {} ({})'.format(data['board_id'], data['sensor_type']))
  return True

def action_helper(data, action, check_if_armed, action_interval, threshold):
  logger.debug('Action helper for data: {}'.format(data))
  now = int(time.time())
  if (check_if_armed) and (not STATUS['armed']):
    logger.info('Check if armed required, but status is not armed')
    return

  action_status.setdefault(data['board_id'], {})
  action_status[data['board_id']].setdefault(data['sensor_type'], 0)

  if (now - action_status[data['board_id']][data['sensor_type']]  > action_interval):
    if (threshold(data['sensor_data']) and action(data)):
      action_status[data['board_id']][data['sensor_type']] = now

class mgmt_Thread(threading.Thread):
  def __init__(self, s, socket):
    threading.Thread.__init__(self)
    self.name = 'mgmt'
    self.daemon = True
    self.socket = socket
    self.serial = s

  def run(self):
    logger.info('Starting')
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
          logger.warning('Got exception \'{}\' while reading from socket'.format(e))
          continue
        if 'action' in data:
          if data['action'] == 'status':
            conn.send(json.dumps(STATUS))
          elif data['action'] == 'send' and 'data' in data:
            try:
              r_cmd = str(str(data['data']['nodeid'])+":"+str(data['data']['cmd']))
              self.serial.write(r_cmd)
            except (IOError, ValueError, serial.serialutil.SerialException) as e:
              logger.error('Fail to send command ({}) to remote node'.format(r_cmd))
          elif data['action'] == 'set' and 'data' in data:
            for key in data['data']:
              logger.warning('Setting {} to {}'.format(key, data['data'][key]))
              STATUS[key] = data['data'][key]
      conn.close()

class failure_dThread(threading.Thread):
  def __init__(self, name, loop_sleep, db_file, cache_time, failure_value, failure_query):
    threading.Thread.__init__(self)
    self.name = name
    self.daemon = True
    self.loop_sleep = loop_sleep
    self.db_file = db_file
    self.cache_time = cache_time
    self.failure_value = failure_value
    self.failure_query = failure_query
    self.failed = {}

  def run(self):
    logger.info('Starting')
    self.db = connect_db(self.db_file)
    while True:
      now = int(time.time())
      if not STATUS[self.name+'_enabled']:
        logger.info('Thread is disabled')
        time.sleep(self.loop_sleep*10)
        continue

      for failed_node, failed_value in self.db.execute(self.failure_query, (self.failure_value, )):
        if failed_node in self.failed:
          if now - self.failed[failed_node] > self.cache_time:
            logger.debug('Removing failed node {} from cache'.format(failed_node))
            del self.failed[failed_node]
        else:
          self.failed[failed_node] = now

          if self.name == 'msd':
            logger.warning('No update from board {} since {} seconds'.format(failed_node,
                now - failed_value))
      time.sleep(self.loop_sleep)

def connect_db(db_file):
  db = sqlite3.connect(db_file)
  return db

def create_db(db_file, create_sensor_table=False):
  db = connect_db()
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

def create_logger(level, log_file, is_daemon):
  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

  if is_daemon:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)
  
  return logger

def ping_gateway(s):
  try:
    s.write('1:1')
  except (IOError, ValueError, serial.serialutil.SerialException) as e:
    logger.error('Failed to get measure from gateway: {}'.format(e))
  time.sleep(1)
  return int(time.time())

def main():

  threading.current_thread().name = 'main'
  logger.info('Starting')

  #[ID][metric:value] / [10][voltage:3.3]
  re_data = re.compile('\[(\d+)\]\[(.+):(.+)\]')

  s = serial.Serial(conf['serial']['device'], conf['serial']['speed'], timeout=conf['serial']['timeout'])
  last_gw_ping = 0

  msd = failure_dThread('msd', conf['loop_sleep'], conf['db_file'],
          conf['msd']['cache_time'], conf['msd']['failure_value'],
          conf['msd']['failure_query']) #Missing sensor detector
  mgmt = mgmt_Thread(s, conf['mgmt_socket'])
  msd.start()
  mgmt.start()

  db = connect_db(conf['db_file'])
  data = {}

  while True:
    try:
      s_data = s.readline().strip()
      m = re_data.match(s_data)
      #{"board_id": 0, "sensor_type": "temperature", "sensor_data": 2}
      data['board_id'], data['sensor_type'], data['sensor_data'] = [m.group(i) for i in range(1, 4)]
    except (IOError, ValueError, serial.serialutil.SerialException) as e:
      logger.error('Got exception \'{}\' while reading from serial'.format(e))
      s.close()
      time.sleep(conf['loop_sleep'])
      try:
        s.open()
      except (OSError) as e:
        logger.warning('Failed to open serial')
      continue
    except (AttributeError) as e:
      if len(s_data) > 0:
        logger.debug('> {}'.format(s_data))
      continue
    finally:
      if (int(time.time()) - last_gw_ping >= conf['gateway_ping_time']):
        last_gw_ping = ping_gateway(s)

    logger.debug('Got data from serial {}'.format(data))

    try:
      db.execute("INSERT INTO sensors(board_id, sensor_type, data) VALUES(?, ?, ?)",
              (data['board_id'], data['sensor_type'], data['sensor_data']))
      db.commit()
    except (sqlite3.IntegrityError) as e:
      logger.error('Integrity error {}'.format(e))
    except (sqlite3.OperationalError) as e:
      time.sleep(random.randint(1,5))
      try:
        db.commit()
      except (sqlite3.OperationalError) as e:
        logger.error('Failed to commit data to DB');

    try:
      action_details = s_type_map[data['sensor_type']]
    except (KeyError) as e:
      logger.debug('Missing s_type_map for sensor_type {}'.format(data['sensor_type']))
      continue

    action_helper(data,
      eval(action_details['action']),
      action_details.get('check_if_armed', 1),
      action_details.get('action_interval', 0),
      eval(action_details.get('threshold', 'lambda x: True')))

def cb_shutdown(message, code):
  logger.info('Stopping')
  logger.info(message)

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config

conf = load_config('global.config.json')
board_map = load_config('boards.config.json')
s_type_map = load_config('sensors.config.json')

logger = create_logger(conf['logging']['level'], conf['logging']['file'], conf['daemon'])

action_status = dict()

STATUS = {
  "armed": 1,
  "msd_enabled": 1,
}

if __name__ == "__main__":
  daemon = daemonocle.Daemon(
          worker=main,
          pidfile=conf['pid_file'],
          shutdown_callback=cb_shutdown,
          detach=conf['daemon'],
          )
  if len(sys.argv) < 2:
    print('Usage: start|stop|restart|status')
    sys.exit(1)
  daemon.do_action(sys.argv[1])
