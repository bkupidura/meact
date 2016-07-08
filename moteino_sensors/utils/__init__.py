from argparse import ArgumentParser
from yaml import load as yaml_load
import logging
import os
import pkgutil
import requests
import sys
import time

from jsonschema import Draft4Validator
from jsonschema.exceptions import ValidationError

from moteino_sensors.utils import schemas

LOG = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as yaml_config:
    config = yaml_load(yaml_config)

  return config


def validate_schema(schema, data):
  try:
    Draft4Validator(schema).validate(data)
  except (ValidationError) as e:
    LOG.warning("Validation failed for data '%s'", data)
    LOG.debug("Error '%s'", e)
    return False, None
  else:
    return True, data


def validate_sensor_data(data):
  return validate_schema(schemas.SCHEMA_SENSOR_DATA, data)


def validate_sensor_config(data):
  try:
    data.setdefault('priority', 500)
    for action in data.get('actions', {}):
      action.setdefault('action_interval', 0)
      action.setdefault('fail_count', 0)
      action.setdefault('fail_interval', 600)
      action.setdefault('message_template', '{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}')
      action.setdefault('threshold', {'lambda': 'lambda: True'})
      action.setdefault('board_ids', [])
      action.setdefault('check_metric', [])
      action.setdefault('check_status', [])
      action.setdefault('action_config', {})
  except (AttributeError, TypeError):
    pass
  return validate_schema(schemas.SCHEMA_SENSOR_CONFIG, data)


def validate_feed_config(data):
  try:
    data.setdefault('feed_interval', 600)
    data.setdefault('fail_interval', 300)
    data.setdefault('params', {})
  except (AttributeError, TypeError):
    pass
  return validate_schema(schemas.SCHEMA_FEED_CONFIG, data)


def create_logger(conf=None):
  if conf is None:
    conf = {}

  logging_level = conf.get('level', logging.INFO)
  logging_file = conf.get('file')
  logging_formatter = conf.get('formatter', '%(asctime)s - %(levelname)s - %(name)s - %(message)s')

  logger = logging.getLogger()
  formatter = logging.Formatter(logging_formatter)

  logger.setLevel(logging_level)

  if logging_file:
    handler = logging.FileHandler(logging_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)


def create_arg_parser(description):
  parser = ArgumentParser(description=description)
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.yaml')
  return parser


def http_request(url, method='GET', params=None, data=None, auth=None, headers=None, verify_ssl=False, timeout=2):
  try:
    req = requests.request(method, url, params=params,
            data=data, headers=headers, auth=auth, verify=verify_ssl, timeout=timeout)
    req.raise_for_status()
  except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
    LOG.error('Fail to connect to url %s', e)
    return None

  return req


def load_mapping(module):
  mapping = {}

  prefix = module.__name__ + '.'
  for _, name, _ in pkgutil.iter_modules(module.__path__):
    m = __import__(prefix + name,
            globals(), locals(), fromlist=[name, ])
    func = getattr(m, name)
    timeout = getattr(m, 'TIMEOUT', 10)
    mapping[name] = {'func': func, 'timeout': timeout}
    # TODO(prmtl): chec with 'inspect.getargspec' if method accepts correct arguments
  return mapping


def treshold_helper(threshold, arg1=None):
  transform = threshold.get('transform')

  if transform:
    transform_result = eval_helper(transform, arg1)
  else:
    transform_result = arg1

  threshold_result = eval_helper(threshold['lambda'], transform_result)

  return transform_result, threshold_result



def eval_helper(threshold_lambda, arg1=None):
  threshold_func = eval(threshold_lambda)
  threshold_func_arg_number = threshold_func.func_code.co_argcount

  try:
    if threshold_func_arg_number == 0:
      threshold_result = threshold_func()
    elif threshold_func_arg_number == 1:
      threshold_result = threshold_func(arg1)
    else:
      LOG.warning('Too much arguments passed to threshold')
  except Exception as e:
    LOG.error("Exception '%s' in lambda '%s' args '%s' '%s'", e, threshold_lambda, arg1, arg2)
    threshold_result = False

  return threshold_result


def prepare_sensor_data(sensor_data):
  validation_result, sensor_data = validate_sensor_data(sensor_data)
  if not validation_result:
    return None

  return sensor_data


def prepare_sensor_data_mqtt(mqtt_msg):
  topic = mqtt_msg.topic.split('/')
  try:
    sensor_data = {
      'board_id': topic[-1],
      'sensor_type': topic[-2],
      'sensor_data': mqtt_msg.payload
    }
  except IndexError:
    LOG.warning("Cant prepare sensor_data from '%s'", mqtt_msg)
    return None

  return prepare_sensor_data(sensor_data)
