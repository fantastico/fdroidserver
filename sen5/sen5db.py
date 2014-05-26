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
        self.scores = self.database['scores']

    def clear(self):
        self.apps.drop()
        self.comments.drop()
        self.scores.drop()
        self.apps = self.database['apps']
        self.comments = self.database['comments']
        self.scores = self.database['scores']

    def format(self, apps):
        result = []
        for app in apps:
            app = app['application']
            app['name'] = {'default': app['name']}
            app['desc'] = {'default': app['desc']}
            app['comments'] = self.init_comments(app['id'])
            app['scores'] = self.init_scores(app['id'])
            result.append(app)
        return result

    def init_comments(self, appid):
        return self.comments.insert({'_id': appid, 'comments': []})

    def init_scores(self, appid):
        return self.scores.insert(
            {'_id': appid, 'user_friendly': 0, 'easy_to_use': 0, 'utility': 0, 'downloads': 0, 'comment': 0,
             'marking': 0})

    def save(self, apps):
    #db.apps.update({'id': app_body['id']}, app_body, upsert=True)
        self.apps.insert(apps)

    def update(self):
        self.clear()
        apps = xml2json.getJson('application')
        apps = self.format(apps)
        self.save(apps)


import pydevd


def update_db():
    pydevd.settrace('192.168.56.1', port=51234, stdoutToServer=True, stderrToServer=True)
    db = Sen5DB(1)
    db.update()


def main():
    update_db()


if __name__ == "__main__":
    main()