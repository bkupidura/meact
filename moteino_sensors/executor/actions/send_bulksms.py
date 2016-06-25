import logging
import sys

from moteino_sensors import utils

LOG = logging.getLogger(__name__)
TIMEOUT=5


def send_bulksms(data, action_config):
  """Send SMS via www.bulksms.com

  Bulksms is HTTP<->SMS gateway.

  MGW configuration:
  action_config = {
    "endpoint": "https://bulksms.vsms.net/eapi/submission/send_sms/2/2.0",
    "user": "bulksms-user",
    "password": "bulksms-password",
    "recipient": ["your-number", "your-number2"],
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending SMS via bulksms.com')

  url = action_config['endpoint']
  params = {
      'username': action_config['user'],
      'password': action_config['password'],
      'msisdn': action_config['recipient'],
      'message': data['message'],
  }

  req = utils.http_request(url, params=params)

  if req:
    result = req.text.split('|')
    if result[0] == '0':
      sys.exit(0)

  LOG.warning('Fail to send SMS via bulksms.com')
  sys.exit(2)
