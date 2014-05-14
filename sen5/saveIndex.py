#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'lijiyang'

from pymongo import MongoClient

import dbConfig


class Sen5DB:
    client = None

    def __init__(self, max_ps=100):
        if Sen5DB.client is None:
            Sen5DB.client = MongoClient(dbConfig.host, dbConfig.port, max_pool_size=max_ps)
        self.database = Sen5DB.client[dbConfig.db]
        self.apps = self.database[dbConfig.apps]


def main():
    db = Sen5DB(1)
    db.apps.insert()


if __name__ == "__main__":
    main()