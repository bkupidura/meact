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

  http_params = feed_config['params']

  url = http_params['url']
  method = http_params.get('method')
  params = http_params.get('params')
  data = http_params.get('data')
  auth_user = http_params.get('auth_user')
  auth_pass = http_params.get('auth_pass')
  headers = http_params.get('headers')
  verify_ssl = http_params.get('verify_ssl', False)
  timeout = http_params.get('timeout', 2)

  if auth_user and auth_pass:
    auth = (auth_user, auth_pass)
  else:
    auth = None
  
  req = utils.http_request(url, method=method,
          params=params, data=data, auth=auth,
          headers=headers, verify_ssl=verify_ssl,
          timeout=timeout)

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
