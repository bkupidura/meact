#!/usr/bin/env python
from multiprocessing import Process, Manager
from threading import Event
import json
import logging
import time

from sqlalchemy.exc import OperationalError

from moteino_sensors import database
from moteino_sensors import mqtt
from moteino_sensors import utils
from moteino_sensors.feeder import feeds


class Feeder(mqtt.Mqtt):
  def __init__(self, db_string, mqtt_config, feeds_map_file):
    super(Feeder, self).__init__()
    self.name = 'feeder'
    self.enabled = Event()
    self.enabled.set()
    self.status = {'feeder': 1}
    self.mqtt_config = mqtt_config
    self.db = database.connect(db_string)
    self.start_mqtt()
    self._validate_feeds(feeds_map_file)

  def _validate_feeds(self, feeds_map_file):
    feeds_map = utils.load_config(feeds_map_file)
    self.feeds_map = dict()

    for feed_name in feeds_map:
      feed_config = feeds_map[feed_name]
      validation_result, feed_config = utils.validate_feed_config(feed_config)

      if validation_result:
        self.feeds_map[feed_name] = feed_config
        self.status[self.name + '/' + feed_name] = 1

  def _feed_helper(self, feed_config):
    feed_name = feed_config['name']
    feed_func = FEEDS_MAPPING.get(feed_name)

    if not feed_func:
      LOG.warning('Unknown feed provider %s', feed_name)
      return

    feed_result = Manager().dict()
    feed_func_timeout = feed_config.get('timeout') or feed_func.get('timeout')

    p = Process(target=feed_func.get('func'), args=(feed_config, feed_result))
    p.start()
    p.join(feed_func_timeout)

    if p.is_alive():
      p.terminate()
      status = 255
    else:
      status = p.exitcode

    if status:
      LOG.error("Fail to execute feed provider '%s', exitcode '%d'", feed_name, status)
      return None
    else:
      return feed_result.get('sensor_data', None)

  def _check_feed_interval(self, feed_name, result, interval):
    try:
      last_feeds = database.get_feed(self.db, feed_name=feed_name,
              result=result,
              last_available=1)
    except OperationalError as e:
      last_feeds = None
      LOG.error("Fail to get feeds '%s'", e)

    if not last_feeds:
      last_feed = 0
    else:
      last_feed = last_feeds[0].last_update

    return utils.time_offset(-last_feed) > interval

  def run(self):
    LOG.info('Starting')
    self.loop_start()
    self.publish_status()
    while True:
      self.enabled.wait()
      for feed_name in self.feeds_map:
        feed_config = self.feeds_map[feed_name]
        feed_enabled = int(self.status.get(self.name + '/' + feed_name, 1))

        if not feed_enabled:
          continue

        if not self._check_feed_interval(feed_name, 0, feed_config['feed_interval']):
          continue

        if not self._check_feed_interval(feed_name, 1, feed_config['fail_interval']):
          continue

        LOG.debug("Geting feeds from '%s'", feed_name)
        feed_result = self._feed_helper(feed_config)

        try:
          if not feed_result:
            database.insert_feed(self.db, feed_name, 1)
            continue
          else:
            database.insert_feed(self.db, feed_name, 0)
        except OperationalError as e:
          LOG.error("Fail to save feed '%s'", e)

        LOG.debug("Got feed provider response '%s'", feed_result)

        for sensor_data in feed_result:
          sensor_data = utils.prepare_sensor_data(sensor_data)
          if sensor_data:
            self.publish_metric(feed_config['mqtt_topic'], sensor_data)

      time.sleep(10)


LOG = logging.getLogger(__name__)
FEEDS_MAPPING = utils.load_mapping(feeds)

def main():
  parser = utils.create_arg_parser('Feeder')
  args = parser.parse_args()

  conf = utils.load_config(args.dir + '/global.yaml')
  conf = conf.get('feeder', {})
  feeds_map_file = args.dir + '/feeds.yaml'

  logging_conf = conf.get('logging', {})
  utils.create_logger(logging_conf)

  feeder = Feeder(db_string=conf['db_string'],
          mqtt_config=conf['mqtt'],
          feeds_map_file=feeds_map_file)
  feeder.run()


if __name__ == "__main__":
  main()
