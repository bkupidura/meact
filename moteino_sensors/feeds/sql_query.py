import logging
import sys

from jq import jq

from moteino_sensors import database


LOG = logging.getLogger(__name__)
TIMEOUT=5


def sql_query(feed_config, feed_result):
  """Get sensor_data from SQL query

  feed_config = {
    "db_string": "sqlite:////etc/mgw/mgw.db",
    "db_query": "SELECT board_id,sensor_data FROM last_metrics"
  }
  """

  LOG.debug('Getting feed from SQL')

  sql_params = {
    'db_string': feed_config['params']['db_string'],
    'db_query': feed_config['params']['db_query']
  }

  db = database.connect(sql_params['db_string'])
  raw_result = db.execute(sql_params['db_query'])

  result = [row.values() for row in raw_result] 

  jq_result = jq(feed_config['expression']).transform(result, multiple_output=True)
  feed_result['sensor_data'] = jq_result

  LOG.debug("Got response from SQL query '%s'", result)
    
  sys.exit(0)
