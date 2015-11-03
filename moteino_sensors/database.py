import sqlite3


def connect(db_file):
  return sqlite3.connect(db_file)
