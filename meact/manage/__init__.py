#!/usr/bin/env python
import logging
import sys

from meact import database
from meact import utils


def get_global_config(config_dir):
  conf = utils.load_config(config_dir + '/global.yaml')
  return conf.get('manage', {})


def create_db(args):
  LOG.info('Creating DB schema')

  db_string = get_global_config(args.dir).get('db_string')
  db = database.connect(db_string)

  database.create_db(db)


def sync_db_desc(args):
  LOG.info('Syncing boards description')

  db_string = get_global_config(args.dir).get('db_string')
  db = database.connect(db_string)
  boards_map = utils.load_config(args.dir + '/boards.yaml')

  database.sync_board(db, boards_map)


def aggregate_metric(args):

  def check_data_type(type_to_check, current_type, sensor_data):
    if not current_type:
      try:
        type_to_check(sensor_data)
        return type_to_check
      except ValueError:
        return None

    return current_type

  def aggregate_metrics(db, start, end, sensor_type, execute):
    metrics = database.get_metric(db, start=start, end=end, sensor_type=sensor_type)
    LOG.info('Got %d metrics between %s and %s', len(metrics), start, end)

    new_records = dict()
    ids_to_delete = []
    for metric in metrics:

      if metric.sensor_type not in new_records:
        data_type = check_data_type(int, None, metric.sensor_data)
        data_type = check_data_type(float, data_type, metric.sensor_data)

        if not data_type:
          LOG.warning("Unknown data type for sensor '%s' data '%s'", metric.sensor_type, metric.sensor_data)
          continue

        new_records[metric.sensor_type] = dict()

        new_records[metric.sensor_type].setdefault('boards', {})
        new_records[metric.sensor_type].setdefault('type', data_type)
        if data_type == float:
          new_records[metric.sensor_type].setdefault('prec', len(metric.sensor_data.split('.')[1]))

      new_records[metric.sensor_type]['boards'].setdefault(metric.board_id, {})
      new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('sensor_sum', 0)
      new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('sensor_num', 0)
      new_records[metric.sensor_type]['boards'][metric.board_id].setdefault('id', metric.id)

      if new_records[metric.sensor_type]['boards'][metric.board_id]['id'] != metric.id:
        ids_to_delete.append(metric.id)

      new_records[metric.sensor_type]['boards'][metric.board_id]['sensor_sum'] += new_records[metric.sensor_type]['type'](metric.sensor_data)
      new_records[metric.sensor_type]['boards'][metric.board_id]['sensor_num'] += 1

    for record in new_records:
      for board in new_records[record]['boards']:
        record_data = new_records[record]['boards'][board]
        new_data = record_data['sensor_sum'] / record_data['sensor_num']

        if new_records[record]['type'] == float:
          new_data = round(new_data, new_records[record]['prec'])

        LOG.info("Update record with id '%d' for sensor_type '%s' for board_id '%s' with value '%s'",
                record_data['id'],
                record,
                board,
                new_data)
        if execute:
          database.update_metric(db, record_data['id'], new_data)

    LOG.info("Delete %d metrics", len(ids_to_delete))
    if execute:
      database.delete_row(db, database.Metric, ids_to_delete)

  # Map policy name to seconds
  policy_map = {
    '10m': 60*10,
    '30m': 60*30,
    'hour': 60*60,
    'day': 60*60*24,
    'week': 60*60*24*7,
    'month': 60*60*24*7*4
  }

  LOG.info('Aggregating metric')

  db_string = get_global_config(args.dir).get('db_string')
  db = database.connect(db_string)
  policy_start = int(args.start)
  policy_end = int(args.start) + policy_map[args.policy]

  while (policy_end <= int(args.end)):
    aggregate_metrics(db, policy_start, policy_end, args.sensor_type, args.execute)
    policy_start += policy_map[args.policy]
    policy_end += policy_map[args.policy]


def clean_action(args):
  LOG.info('Cleaning action table')

  db_string = get_global_config(args.dir).get('db_string')
  db = database.connect(db_string)

  actions = database.get_action(db, start=args.start, end=args.end)
  LOG.info('Got %d actions between %s and %s', len(actions), args.start, args.end)

  ids_to_delete = [action.id for action in actions]

  if args.execute:
    database.delete_row(db, database.Action, ids_to_delete)


def clean_feed(args):
  LOG.info('Cleaning feeds table')

  db_string = get_global_config(args.dir).get('db_string')
  db = database.connect(db_string)

  feeds = database.get_feed(db, start=args.start, end=args.end)
  LOG.info('Got %d feeds between %s and %s', len(feeds), args.start, args.end)

  ids_to_delete = [feed.id for feed in feeds]

  if args.execute:
    database.delete_row(db, database.Feed, ids_to_delete)


def main():
  parser = utils.create_arg_parser('Meact Manage CLI')
  subparsers = parser.add_subparsers()

  p_create_db = subparsers.add_parser('create-db', help='Create meact database. CAUTION: IT WILL REMOVE OLD DATA')
  p_create_db.set_defaults(func=create_db)

  p_sync_db_desc = subparsers.add_parser('sync-db-desc', help='Sync boards description')
  p_sync_db_desc.set_defaults(func=sync_db_desc)

  p_aggregate_metric = subparsers.add_parser('aggregate-metric', help='Aggregate metrics in DB')
  p_aggregate_metric.add_argument('--start', required=True, help='Start time for aggregate (seconds since epoch)')
  p_aggregate_metric.add_argument('--end', required=True, help='End time for aggregate (seconds since epoch)')
  p_aggregate_metric.add_argument('--policy', required=True, help='Aggregate policy, aggregate per 10m/30m/hour/day/week/month')
  p_aggregate_metric.add_argument('--sensor-type', required=False, help='sensor_type for aggregate, if missing we will aggregate all sensor_type')
  p_aggregate_metric.add_argument('--execute', required=False, help='Execute data aggregation, without this DB will not be changed', action="store_true")
  p_aggregate_metric.set_defaults(func=aggregate_metric)

  p_clean_action = subparsers.add_parser('clean-action', help='Clean (remove) old records from action table')
  p_clean_action.add_argument('--start', required=True, help='Start time for cleaning (seconds since epoch)')
  p_clean_action.add_argument('--end', required=True, help='End time for cleaning (seconds since epoch)')
  p_clean_action.add_argument('--execute', required=False, help='Execute data cleaning, without this DB will not be changed', action="store_true")
  p_clean_action.set_defaults(func=clean_action)

  p_clean_feed = subparsers.add_parser('clean-feed', help='Clean (remove) old records from feed table')
  p_clean_feed.add_argument('--start', required=True, help='Start time for cleaning (seconds since epoch)')
  p_clean_feed.add_argument('--end', required=True, help='End time for cleaning (seconds since epoch)')
  p_clean_feed.add_argument('--execute', required=False, help='Execute data cleaning, without this DB will not be changed', action="store_true")
  p_clean_feed.set_defaults(func=clean_feed)

  args = parser.parse_args()

  utils.create_logger()

  args.func(args)


LOG = logging.getLogger(__name__)

if __name__ == "__main__":
  main()
