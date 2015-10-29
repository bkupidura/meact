#!/usr/bin/python
import requests
import sys
import os
import json
import time
import logging
import argparse

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError("Config '{}' is missing".format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config

def create_logger(level, log_file=None):
  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

  if log_file:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)

def api_request(url, method='GET', params=None, data=None, auth=None, headers=None, verify_ssl=False):
  logging.getLogger("urllib3").setLevel(logging.CRITICAL)
  try:
    req = requests.request(method, url, params=params,
            data=data, headers=headers, auth=auth, verify=verify_ssl, timeout=2)
    req.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.error('Fail to connect to url %s', e)
    return {}
  try:
    data = json.loads(req.text)
  except (ValueError) as e:
    return {}
  return data

def set_armed(mgw_api, status=0):
  params = {'armed': status}
  result = api_request('{}/action/status'.format(mgw_api),
          method='POST', data=json.dumps(params),
          headers={'content-type': 'application/json'})

def check_action(data, allowed_devices, armed, mgw_api):
  status = {
    'enter': 0,
    'exit': 0,
  }
  for device in data:
    action = data[device]['action']
    if device in allowed_devices:
      try:
        status[action] += 1
      except (KeyError):
        pass

  if (armed == 1) and (status['enter'] > 0):
    LOG.info('Disarm alarm')
    set_armed(mgw_api, 0)
  elif (armed == 0) and (status['exit'] == len(allowed_devices)):
    LOG.info('Arm alarm')
    set_armed(mgw_api, 1)

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Fence')
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
  args = parser.parse_args()

  conf = load_config(args.dir + '/global.config.json')
  create_logger(logging.INFO)

  LOG.info('Starting')
  while True:
    mgw_status = api_request('{}/action/status'.format(conf['mgw_api']))
    if mgw_status.get('fence'):
      req = api_request(conf['geo_api'], auth=(conf['geo_user'], conf['geo_pass']))
      if req:
        check_action(req, conf['geo_devices'], mgw_status.get('armed'), conf['mgw_api'])
      else:
        set_armed(conf['mgw_api'], 1)

    time.sleep(conf['loop_time'])
