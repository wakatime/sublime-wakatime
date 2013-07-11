""" ==========================================================
File:        sublime-wakatime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  Wakati.Me <support@wakatime.com>
Website:     https://www.wakati.me/
==========================================================="""

__version__ = '0.2.1'

import time
import uuid
from os.path import expanduser, dirname, realpath, isfile
from subprocess import call, Popen

import sublime
import sublime_plugin


# globals
AWAY_MINUTES = 10
ACTION_FREQUENCY = 5
PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/packages/wakatime/wakatime.py' % PLUGIN_DIR
LAST_ACTION = 0
LAST_USAGE = 0
LAST_FILE = None


# To be backwards compatible, rename config file
if isfile(expanduser('~/.wakatime')):
    call([
        'mv',
        expanduser('~/.wakatime'),
        expanduser('~/.wakatime.conf')
    ])


# Create config file if it does not already exist
if not isfile(expanduser('~/.wakatime.conf')) or True:
    def got_key(text):
        if text:
            cfg = open(expanduser('~/.wakatime.conf'), 'w')
            cfg.write('api_key=%s' % text)
            cfg.close()
    sublime.active_window().show_input_panel('Enter your WakaTi.me api key:', '', got_key, None, None)


def api(targetFile, timestamp, isWrite=False, endtime=None):
    global LAST_ACTION, LAST_USAGE, LAST_FILE
    if not targetFile:
        targetFile = LAST_FILE
    if targetFile:
        cmd = ['python', API_CLIENT,
            '--file', targetFile,
            '--time', str('%f' % timestamp),
            '--plugin', 'sublime-wakatime/%s' % __version__,
            #'--verbose',
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
        LAST_USAGE = LAST_ACTION


def away(now):
    duration = now - LAST_USAGE
    units = 'seconds'
    if duration > 59:
        duration = int(duration / 60)
        units = 'minutes'
    if duration > 59:
        duration = int(duration / 60)
        units = 'hours'
    if duration > 24:
        duration = int(duration / 24)
        units = 'days'
    return sublime\
        .ok_cancel_dialog("You were away %d %s. Add time to current file?"\
        % (duration, units), 'Yes, log this time')


def enough_time_passed(now):
    if now - LAST_ACTION > ACTION_FREQUENCY * 60:
        return True
    return False


def should_prompt_user(now):
    if not LAST_USAGE:
        return False
    duration = now - LAST_USAGE
    if duration > AWAY_MINUTES * 60:
        return True
    return False


def handle_write_action(view):
    now = time.time()
    targetFile = view.file_name()
    if enough_time_passed(now) or targetFile != LAST_FILE:
        if should_prompt_user(now):
            if away(now):
                api(targetFile, now, endtime=LAST_ACTION, isWrite=True)
            else:
                api(targetFile, now, isWrite=True)
        else:
            api(targetFile, now, endtime=LAST_ACTION, isWrite=True)
    else:
        api(targetFile, now, isWrite=True)


def handle_normal_action(view):
    global LAST_USAGE
    now = time.time()
    targetFile = view.file_name()
    if enough_time_passed(now) or targetFile != LAST_FILE:
        if should_prompt_user(now):
            if away(now):
                api(targetFile, now, endtime=LAST_ACTION)
            else:
                api(targetFile, now)
        else:
            api(targetFile, now, endtime=LAST_ACTION)
    else:
        LAST_USAGE = now


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        handle_write_action(view)

    def on_activated(self, view):
        handle_normal_action(view)

    def on_selection_modified(self, view):
        handle_normal_action(view)

