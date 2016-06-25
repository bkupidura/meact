import logging
import sys

LOG = logging.getLogger(__name__)
TIMEOUT=5

def log(data, action_config):
  """Log action

  Allow to push message to executor log
  """
  LOG.info("Log action '%s'", data['message'])
  sys.exit(0)
