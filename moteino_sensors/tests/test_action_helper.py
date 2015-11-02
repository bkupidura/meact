import copy
import os
import sys

import pytest

from moteino_sensors import gateway

default_action = {
  'check_if_armed': {
    'default': True,
    'except': [],
  },
  'action_interval': 0,
  'threshold': 'lambda x: True',
  'fail_count': 0,
  'fail_interval': 0,
}


board_id = 1
check_test_data = (
  (
    {
      'default': True,
      'except': [],
    },
    True
  ),
  (
    {
      'default': False,
      'except': [],
    },
    False
  ),
  (
    {
      'default': True,
      'except': [board_id, ],
    },
    False
  ),
  (
    {
      'default': False,
      'except': [board_id, ],
    },
    True
  ),
  (
    {
      'default': True,
      'except': [board_id + 10, ],
    },
    True
  ),
)

@pytest.mark.parametrize('check_if_armed, expected', check_test_data)
def test_should_check_if_armed(check_if_armed, expected):
  action_details = copy.deepcopy(default_action)
  action_details['check_if_armed'] = check_if_armed

  ada = gateway.ActionDetailsAdapter(action_details)

  assert ada.should_check_if_armed(board_id) == expected
