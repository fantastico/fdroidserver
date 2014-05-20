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
        self.apps = self.database['apps']
        self.comments = self.database['comments']

    def clear(self):
        self.apps.drop()
        self.comments.drop()
        self.apps = self.database['apps']
        self.comments = self.database['comments']


def add_comment(app, db):
    comment_id = db.comments.insert({})
    app['comments'] = comment_id


import pydevd


def main():
    pydevd.settrace('192.168.56.1', port=51234, stdoutToServer=True, stderrToServer=True)
    db = Sen5DB(1)
    db.clear()
    apps = xml2json.getJson('application')
    for app in apps:
        app_body = app['application']
        add_comment(app_body, db)
        #db.apps.update({'id': app_body['id']}, app_body, upsert=True)
        db.apps.insert(app_body)


if __name__ == "__main__":
    main()