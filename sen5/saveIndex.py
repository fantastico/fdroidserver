#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'lijiyang'

from pymongo import MongoClient
import xml2json
import config


class Sen5DB:
    client = None

    """ input: max_ps, maximum number of connections in the pool """

    def __init__(self, max_ps=100):
        if Sen5DB.client is None:
            Sen5DB.client = MongoClient(config.host, config.port, max_pool_size=max_ps)
        self.database = Sen5DB.client[config.db]
        self.apps = self.database[config.apps]


import pydevd


def main():
    pydevd.settrace('192.168.56.1', port=51234, stdoutToServer=True, stderrToServer=True)
    db = Sen5DB(1)
    apps = xml2json.getJson()
    for app in apps:
        appbody = app['application']
        db.apps.update({'id': appbody['id']}, appbody, upsert=True)


if __name__ == "__main__":
    main()