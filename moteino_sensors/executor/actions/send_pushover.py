import json
import logging
import sys

from moteino_sensors import utils


LOG = logging.getLogger(__name__)
TIMEOUT=5


def send_pushover(data, action_config):
  """Send notification via pushover.net

  Allow to send notification via pushover.net.

  MGW configuration:
  action_config = {
    "token": "auth_token",
    "user_key": "user_or_group_key",
    "endpoint": "https://api.instapush.im/v1/post",
    "priority": 0,
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending notification via pushover.net')

  url = action_config['endpoint']
  params = {
    'token': action_config['token'],
    'user': action_config['user_key'],
    'priority': action_config.get('priority', 0),
    'message': data['message']
  }

  req = utils.http_request(url, method='POST', data=params)

  if not req:
    LOG.warning('Fail to send notification via pushover.net')
    sys.exit(2)

  try:
    response = json.loads(req.text)
  except (ValueError, TypeError):
    LOG.warning('Fail to send notification via pushover.net')
    sys.exit(2)

  if not response.get('status'):
    LOG.warning('Fail to send notification via pushover.net')
    sys.exit(2)

  sys.exit(0)
