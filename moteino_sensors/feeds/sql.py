import json
import logging
import sys

from jq import jq

from moteino_sensors import utils
from moteino_sensors import database


LOG = logging.getLogger(__name__)


def sql(feed, feed_result):
  """Get sensor_data from SQL query

  """

  LOG.info('Getting feed from SQL')

  sql_params = feed['params']

  db_string = sql_params['db_string']
  db_query = sql_params['db_query']

  db = database.connect(db_string)
  raw_result = db.execute(db_query)

  result = [row.values() for row in raw_result] 

  jq_result = jq(feed['jq_expression']).transform(result, multiple_output=True)

  feed_result['sensor_data'] = jq_result
    
  sys.exit(0)
