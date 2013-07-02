""" ======================================================
File:        sublime-wakatime.py
Description: Automatic time tracking for Sublime Text 2.
Maintainer:  Wakati.Me <support@wakatime.com>
Version:     0.1.0
======================================================="""


import time
import uuid
from os.path import expanduser, dirname, realpath
from subprocess import call, Popen

import sublime
import sublime_plugin


# Create logfile if does not exist
call(['touch', '~/.wakatime.log'])

PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/libs/wakatime.py' % PLUGIN_DIR
INSTANCE_ID = str(uuid.uuid4())


def get_api_key():
    api_key = None
    try:
        cf = open(expanduser('~/.wakatime'))
        for line in cf:
            line = line.split('=', 1)
            if line[0] == 'api_key':
                api_key = line[1].strip()
        cf.close()
    except IOError:
        pass
    return api_key


def api(action, task, timestamp):
    if task:
        api_key = get_api_key()
        if api_key:
            cmd = ['python', API_CLIENT,
                '--key', api_key,
                '--instance', INSTANCE_ID,
                '--action', action,
                '--task', task,
                '--time', str('%f' % timestamp)]
            Popen(cmd)


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        api('write_file', view.file_name(), time.time())

    def on_activated(self, view):
        api('open_file', view.file_name(), time.time())

    def on_deactivated(self, view):
        api('close_file', view.file_name(), time.time())


if get_api_key() is None:
    sublime.error_message('Missing your Wakati.Me api key')
