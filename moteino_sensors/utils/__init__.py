from argparse import ArgumentParser
import json
import logging
import os
import pkgutil
import requests
import sys
import time

from jsonschema import Draft4Validator, validators
from jsonschema.exceptions import ValidationError

from moteino_sensors import actions
from moteino_sensors import feeds
from moteino_sensors.utils import schemas

LOG = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def load_config(config_name):
  if not os.path.isfile(config_name):
    raise KeyError('Config {} is missing'.format(config_name))

  with open(config_name) as json_config:
    config = json.load(json_config)

  return config


def extend_with_default(validator_class):
  validate_properties = validator_class.VALIDATORS["properties"]

  def set_defaults(validator, properties, instance, schema):
    for property, subschema in properties.iteritems():
      if "default" in subschema:
        instance.setdefault(property, subschema["default"])

    for error in validate_properties(
      validator, properties, instance, schema,
    ):
      yield error

  return validators.extend(
    validator_class, {"properties" : set_defaults},
  )


def validate_schema(schema, data):
  ExtendDefaultDraft4Validator = extend_with_default(Draft4Validator)
  try:
    Draft4Validator(schema).validate(data)
  except (ValidationError) as e:
    LOG.warning("Validation failed for data '%s'", data)
    LOG.debug("Error '%s'", e)
    return False, None
  else:
    ExtendDefaultDraft4Validator(schema).validate(data)
    return True, data


def validate_sensor_data(data):
  return validate_schema(schemas.SCHEMA_SENSOR_DATA, data)


def validate_sensor_config(data):
  return validate_schema(schemas.SCHEMA_SENSOR_CONFIG, data)

def validate_feed_config(data):
  return validate_schema(schemas.SCHEMA_FEED_CONFIG, data)


def create_logger(conf=None):
  if conf is None:
    conf = {}

  level = conf.get('level', logging.INFO)
  log_file = conf.get('file')

  logger = logging.getLogger()
  logger.setLevel(level)
  formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

  if log_file:
    handler = logging.FileHandler(log_file)
  else:
    handler = logging.StreamHandler(sys.stdout)

  handler.setFormatter(formatter)
  logger.addHandler(handler)


def create_arg_parser(description):
  parser = ArgumentParser(description=description)
  parser.add_argument('--dir', required=True, help='Root directory, should cotains *.config.json')
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


def load_json(data):
  try:
    return json.loads(data)
  except (ValueError, TypeError) as e:
    return {}


def load_actions():
    mapping = {}

    prefix = actions.__name__ + '.'
    for _, action_name, _ in pkgutil.iter_modules(actions.__path__):
        action_module = __import__(prefix + action_name,
                                   globals(), locals(), fromlist=[action_name, ])
        action_func = getattr(action_module, action_name)
        timeout = getattr(action_module, 'TIMEOUT', 10)
        mapping[action_name] = {'func': action_func, 'timeout': timeout}
        # TODO(prmtl): chec with 'inspect.getargspec' if method accepts correct arguments
    return mapping


def load_feeds():
    mapping = {}

    prefix = feeds.__name__ + '.'
    for _, feed_name, _ in pkgutil.iter_modules(feeds.__path__):
        feed_module = __import__(prefix + feed_name,
                                   globals(), locals(), fromlist=[feed_name, ])
        feed_func = getattr(feed_module, feed_name)
        timeout = getattr(feed_module, 'TIMEOUT', 10)
        mapping[feed_name] = {'func': feed_func, 'timeout': timeout}
        # TODO(prmtl): chec with 'inspect.getargspec' if method accepts correct arguments
    return mapping


def eval_helper(threshold_lambda, arg1=None, arg2=None):
  threshold_func = eval(threshold_lambda)
  threshold_func_arg_number = threshold_func.func_code.co_argcount

  try:
    if threshold_func_arg_number == 0:
      threshold_result = threshold_func()
    elif threshold_func_arg_number == 1:
      threshold_result = threshold_func(arg1)
    elif threshold_func_arg_number == 2:
      try:
        threshold_result = threshold_func(arg1, arg2)
      except (IndexError):
        LOG.info('Not enough values stored to check threshold')
        threshold_result = False
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
