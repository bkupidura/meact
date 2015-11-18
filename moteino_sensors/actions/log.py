import logging
import sys

LOG = logging.getLogger(__name__)
TIMEOUT=5

def log(data, action_config):
  LOG.info("Log action '%s'", data['message'])
  sys.exit(0)
