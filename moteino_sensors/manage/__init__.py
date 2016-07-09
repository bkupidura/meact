#!/usr/bin/env python
import logging
import sys

from moteino_sensors import database
from moteino_sensors import utils

def create_db(db):
  LOG.info('Creating DB schema')
  database.create_db(db)

def sync_db_desc(db, boards_map):
  LOG.info('Syncing boards description')
  database.sync_boards(db, boards_map)

def main():
  parser = utils.create_arg_parser('Manage')
  parser.add_argument('--create-db', required=False, help='Create mgw database. CAUTION: IT WILL REMOVE OLD DATA', action="store_true")
  parser.add_argument('--sync-db-desc', required=False, help='Sync boards description', action="store_true")
  args = parser.parse_args()

  utils.create_logger()

  conf = utils.load_config(args.dir + '/global.yaml')
  conf = conf.get('manage', {})
  boards_map = utils.load_config(args.dir + '/boards.yaml')
  db = database.connect(conf['db_string'])

  if args.create_db:
    create_db(db)

  if args.sync_db_desc:
    sync_db_desc(db, boards_map)

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
  main()
