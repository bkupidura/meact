#!/usr/bin/env python
import logging
import time


from moteino_sensors import utils
from moteino_sensors.dbaq import DBQuery


class Msd(DBQuery):

  name = 'msd'

  def _handle_result(self, board_id, value):
    now = int(time.time())
    last_seen = now - value
    if utils.eval_helper(self.threshold, last_seen):
      LOG.debug("Board '%s' last seen '%s' seconds ago", board_id, last_seen)
      data = {'board_id': board_id,
              'sensor_data': str(last_seen),
              'sensor_type': self.name}
      self.publish(self.mqtt_config['topic']['mgw/action'], data)


LOG = logging.getLogger(__name__)

def main():
  parser = utils.create_arg_parser('MSD - missing sensor detector')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.config.json')

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  msd = Msd(conf=conf)
  msd.run()


if __name__ == "__main__":
  main()
