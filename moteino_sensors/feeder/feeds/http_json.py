import json
import logging
import sys

from jq import jq

from moteino_sensors import utils


LOG = logging.getLogger(__name__)
TIMEOUT=5

def http_json(feed_config, feed_result):
  """Get sensor_data from HTTP JSON API

  feed_config = {
    "url": "http://example.com/api",
    "auth_user": "user",
    "auth_pass": "pass"
  }
  """

  LOG.debug('Getting feed from HTTP')

  http_params = {
    'url': feed_config['params']['url'],
    'method': feed_config['params'].get('method'),
    'params': feed_config['params'].get('params'),
    'data': feed_config['params'].get('data'),
    'headers': feed_config['params'].get('headers'),
    'verify_ssl': feed_config['params'].get('verify_ssl', False),
    'timeout': feed_config['params'].get('timeout', 2)
  }


  if feed_config['params'].get('auth_user') and feed_config['params'].get('auth_pass'):
    http_params['auth'] = (feed_config['params']['auth_user'], feed_config['params']['auth_pass'])
  else:
    http_params['auth'] = None

  req = utils.http_request(http_params['url'],
          method=http_params['method'],
          params=http_params['params'],
          data=http_params['data'],
          auth=http_params['auth'],
          headers=http_params['headers'],
          verify_ssl=http_params['verify_ssl'],
          timeout=http_params['timeout'])

  if not req:
    LOG.warning("Fail to get feeds from '%s'", url)
    sys.exit(2)

  try:
    response = json.loads(req.text)
  except (ValueError, TypeError):
    LOG.warning("No response from '%s'", url)
    sys.exit(2)

  jq_result = jq(feed_config['expression']).transform(response, multiple_output=True)
  feed_result['sensor_data'] = jq_result

  LOG.debug("Got response from HTTP '%s'", response)

  sys.exit(0)
