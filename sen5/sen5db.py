#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'lijiyang'

from pymongo import MongoClient
import xml2json
import config

score = {
    '_id': 'test',
    'score': 0,
    'downloads': 0,
    'comment': 0,
    'marking': 0,
    'pictures': [
        'http://192.168.0.8/kenrepo/icons-640/com.sen5.android.remoteServer.20140930.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sodao.12.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sen5.android.remoteServer.20140930.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sodao.12.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sen5.android.remoteServer.20140930.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sodao.12.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sen5.android.remoteServer.20140930.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sodao.12.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sen5.android.remoteServer.20140930.png',
        'http://192.168.0.8/kenrepo/icons-640/com.sodao.12.png'
    ]
}

common_repository = {
    '_id': 'common',
    'version': 0,
    'conditions': {},
    'apps': []
}

app_test = {
    '_id': 'test'
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
        self.comments = self.database['comments']
        self.scores = self.database['scores']

    def check_app_group_exist(self, app_search_condition):
        result = self.repositories.find_one(app_search_condition, {'_id': 1})
        if result is None:
            return False
        else:
            return True

    def create_common_repository(self):
        return self.repositories.insert(common_repository)

    def insert_app(self, app):
        return self.apps.insert(app)

    def find_app(self, query):
        return self.apps.find_one(query)

    def update_app(self, app):
        self.apps.update({'_id': app['_id']}, {'$set': app})

    def add_apk(self, _id, apk):
        self.apps.update({'_id': _id}, {'$push': {'package': apk}})

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
            app['scores'] = self.add_scores(app['id'])
            result.append(app)
        return result

    def init_comments(self, appid):
        return self.comments.insert({'_id': appid, 'comments': []})

    def add_scores(self, appid):
        score['_id'] = appid
        return self.scores.insert(score)

    def save(self, apps):
        self.apps.insert(apps)

    def update(self):
        self.clear()
        apps = xml2json.getJson('application')
        if len(apps) > 0:
            apps = self.format(apps)
            self.save(apps)

    def init_scores(self):
        ids = self.apps.find({}, {'_id': 1})
        for app_id in ids:
            result = self.scores.find_one({'_id': app_id}, {'_id': 1})
            if result is None:
                score['_id'] = app_id['_id']
                self.scores.insert(score)
                print 'init scores for app id=' + str(app_id['_id'])

    def update_repo(self, repo_id, app_id):
        self.repositories.update({'_id': repo_id}, {'$addToSet': {'apps': app_id}, '$inc': {'version': 1}})

    def init_db(self):
        self.repositories.insert(common_repository)
        self.scores.insert(score)
        # self.apps.insert(app_test)


def update_db():
    db = Sen5AppsDB()
    db.update()
    # result = db.create_common_repository()
    # print result


# import pydevd
# pydevd.settrace('192.168.0.123', port=51234, stdoutToServer=True, stderrToServer=True)


def main():
    db = Sen5AppsDB()
    db.init_db()
    print 'Database initialized!'


if __name__ == "__main__":
    main()