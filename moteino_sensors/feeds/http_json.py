import json
import logging
import sys

from jq import jq

from moteino_sensors import utils


LOG = logging.getLogger(__name__)


def http_json(feed, feed_result):
  """Get sensor_data from HTTP JSON API

  """

  LOG.info('Getting feed from HTTP')

  http_params = feed['params']

  url = http_params['url']
  method = http_params.get('method')
  auth_user = http_params.get('auth_user')
  auth_pass = http_params.get('auth_pass')

  if auth_user and auth_pass:
    auth = (auth_user, auth_pass)
  else:
    auth = None
  
  req = utils.http_request(url, method=method, auth=auth)
  response = utils.load_json(req.text)

  if not req:
    LOG.warning('Fail to get feeds')
    sys.exit(2)

  jq_result = jq(feed['jq_expression']).transform(response, multiple_output=True)
  feed_result['sensor_data'] = jq_result
    
  sys.exit(0)
