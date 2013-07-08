""" ==========================================================
File:        sublime-wakatime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  Wakati.Me <support@wakatime.com>
Website:     https://www.wakati.me/
==========================================================="""

__version__ = '0.2.1'

import time
import uuid
from os.path import expanduser, dirname, realpath
from subprocess import call, Popen

import sublime
import sublime_plugin


# Prompt user if no activity for this many minutes
AWAY_MINUTES = 10

# globals
PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/packages/wakatime/wakatime.py' % PLUGIN_DIR
LAST_ACTION = 0
LAST_FILE = None


def api(targetFile, timestamp, isWrite=False, endtime=None):
    global LAST_ACTION, LAST_FILE
    if not targetFile:
        targetFile = LAST_FILE
    if targetFile:
        cmd = ['python', API_CLIENT,
            '--file', targetFile,
            '--time', str('%f' % timestamp),
            '--plugin', 'sublime-wakatime/%s' % __version__,
        ]
        if isWrite:
            cmd.append('--write')
        if endtime:
            cmd.extend(['--endtime', str('%f' % endtime)])
        Popen(cmd)
        LAST_ACTION = timestamp
        if endtime and endtime > LAST_ACTION:
            LAST_ACTION = endtime
        LAST_FILE = targetFile


def away(now):
    if LAST_ACTION == 0:
        return False
    duration = now - LAST_ACTION
    if duration > AWAY_MINUTES * 60:
        duration = int(duration)
        units = 'seconds'
        if duration > 60:
            duration = int(duration / 60.0)
            units = 'minutes'
        if duration > 60:
            duration = int(duration / 60.0)
            units = 'hours'
        return sublime\
            .ok_cancel_dialog("You were away %d %s. Add time to current file?"\
            % (duration, units), 'Yes, log this time')


def enough_time_passed(now):
    return (now - LAST_ACTION >= 5 * 60)


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        api(view.file_name(), time.time(), isWrite=True)

    def on_activated(self, view):
        now = time.time()
        if enough_time_passed(now):
            if away(now):
                api(view.file_name(), LAST_ACTION, endtime=now)
            else:
                api(view.file_name(), now)

    def on_selection_modified(self, view):
        now = time.time()
        if enough_time_passed(now):
            if away(now):
                api(view.file_name(), LAST_ACTION, endtime=now)
            else:
                api(view.file_name(), now)

