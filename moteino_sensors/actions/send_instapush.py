import json
import logging
import requests
import sys


LOG = logging.getLogger(__name__)
TIMEOUT=5


logging.getLogger("requests").setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings()

def send_instapush(data, action_config):
  """Send notification via instapush.im

  Allow to send notification to multiple apps (users).
  Instapush configuration:
  - Application name - rpi
  - Event title - event_name
  - Trackers - message
  - Push message - RPI notification: {message}

  MGW configuration:
  action_config = {
    "event": "event_name",
    "endpoint": "https://api.instapush.im/v1/post",
    "apps": [
      {"id": "instapush-app-id", "secret": "instapush-app-secret"}
    ],
    "enabled": 1
  }
  """
  if not action_config.get('enabled'):
    sys.exit(1)

  LOG.info('Sending notification via instapush.im')

  url = action_config['endpoint']
  params = {
    'event': action_config['event'],
    'trackers': {
      'message': data['message']
    }
  }

  for app in action_config['apps']:
    headers = {
      'Content-Type': 'application/json',
      'x-instapush-appid': app['id'],
      'x-instapush-appsecret': app['secret']
    }
    try:
      r = requests.post(url, data=json.dumps(params), headers=headers)
      r.raise_for_status()
    except (requests.HTTPError, requests.ConnectionError, requests.exceptions.Timeout) as e:
      LOG.warning("Got exception '%s' in send_instapush", e)
      sys.exit(2)

  sys.exit(0)
