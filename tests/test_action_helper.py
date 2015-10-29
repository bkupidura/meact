import copy
import os
import sys

import pytest

# NOTE(prmtl): hack to allow imports of mgw.py
# it should be replaced by a real life file but do we
# really care about it? :)
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
import mgw


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

  ada = mgw.ActionDetailsAdapter(action_details)

  assert ada.should_check_if_armed(board_id) == expected
