#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'lijiyang'

from pymongo import MongoClient
import xml2json
import config


class Sen5DB:
    client = None

    """ input: max_ps, maximum number of connections in the pool """

    def __init__(self, max_ps=20):
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
        # db.apps.update({'id': app_body['id']}, app_body, upsert=True)
        self.apps.insert(apps)

    def update(self):
        self.clear()
        apps = xml2json.getJson('application')
        if len(apps) > 0:
            apps = self.format(apps)
            self.save(apps)


common_repository = {
    '_id': 'common',
    'conditions': {},

}


class Sen5AppsDB:
    __client = None

    def __init__(self, max_ps=2):
        if Sen5AppsDB.__client is None:
            Sen5AppsDB.__client = MongoClient(config.host, config.port, max_pool_size=max_ps)
        self.database = Sen5AppsDB.__client[config.db]
        self.apps = self.database['apps']
        self.repositories = self.database['repositories']
        self.main_repo = self.database['main_repo']

    def check_app_group_exist(self, app_search_condition):
        result = self.apps.find_one(app_search_condition, {'_id': 1})
        if result is None:
            return False
        else:
            return True

    def create_common_repository(self):
        return self.apps.insert(common_repository)

    def insert_app(self, app):
        return self.apps.insert(app)

    def find_app(self, query):
        return self.apps.find_one(query)


def update_db():
    # db = Sen5DB(1)
    # db.update()
    db = Sen5AppsDB()
    result = db.create_common_repository()
    print result



def main():
    update_db()


if __name__ == "__main__":
    main()