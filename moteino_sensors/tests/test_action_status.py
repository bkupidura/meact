import copy
import hashlib
import os
import sys
import time

import pytest

from moteino_sensors import executor

board_id = '1'
sensor_type = 'test'

action_status_id = board_id + sensor_type
action_status_id_hex = hashlib.md5(action_status_id).hexdigest()
sensor_config_id = 'test'

action_status = executor.ActionStatusAdapter()
action_status.build_defaults(action_status_id_hex,
        sensor_config_id,
        board_id,
        sensor_type)

def build_action_status(action_status):
  action_status[action_status_id_hex][sensor_config_id]['last_fail'] = \
        [int(time.time()) - i for i in xrange(10)]

  action_status[action_status_id_hex][sensor_config_id]['last_action'] = int(time.time())

  return action_status

clean_failed_test_data = (
  (
    0,
    (0, 0)
  ),
  (
    5,
    (1, 9)
  ),
  (
    100,
    (10, 10)
  ),
)

@pytest.mark.parametrize('fail_interval, expected', clean_failed_test_data)
def test_clean_failed(fail_interval, expected):
  test_action_status = copy.deepcopy(action_status)
  test_action_status = build_action_status(test_action_status)

  test_action_status.clean_failed(action_status_id_hex,
          sensor_config_id,
          fail_interval)

  ada = len(test_action_status[action_status_id_hex][sensor_config_id]['last_fail'])

  assert ada >= expected[0]
  assert ada <= expected[1]

check_failed_test_data = (
  (
    0,
    (True, 10)
  ),
  (
    10,
    (True, 10)
  ),
  (
    11,
    (False, 11)
  ),
  (
    12,
    (False, 11)
  ),
  (
    20,
    (False, 11)
  ),
)

@pytest.mark.parametrize('fail_count, expected', check_failed_test_data)
def test_check_failed(fail_count, expected):
  test_action_status = copy.deepcopy(action_status)
  test_action_status = build_action_status(test_action_status)

  result = test_action_status.check_failed_count(action_status_id_hex,
          sensor_config_id,
          fail_count)

  ada = len(test_action_status[action_status_id_hex][sensor_config_id]['last_fail'])

  assert result == expected[0]
  assert ada == expected[1]

check_last_action_test_data = (
  (
    0,
    False
  ),
  (
    -1,
    True
  ),
)

@pytest.mark.parametrize('action_interval, expected', check_last_action_test_data)
def test_last_action(action_interval, expected):
  test_action_status = copy.deepcopy(action_status)
  test_action_status = build_action_status(test_action_status)

  ada = test_action_status.check_last_action(action_status_id_hex,
          sensor_config_id,
          action_interval)

  assert ada == expected
