""" ==========================================================
File:        sublime-wakatime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTi.me <support@wakatime.com>
Website:     https://www.wakati.me/
==========================================================="""

__version__ = '0.2.10'

import sublime
import sublime_plugin

import glob
import os
import platform
import time
import uuid
from os.path import expanduser, dirname, realpath, isfile, join, exists
from subprocess import call, Popen


# globals
AWAY_MINUTES = 10
ACTION_FREQUENCY = 5
PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/packages/wakatime/wakatime-cli.py' % PLUGIN_DIR
SETTINGS = '%s.sublime-settings' % __name__
LAST_ACTION = 0
LAST_USAGE = 0
LAST_FILE = None
BUSY = False


# Convert ~/.wakatime.conf to WakaTime.sublime-settings
def convert_config_to_sublime_settings():
    # To be backwards compatible, rename config file
    settings = sublime.load_settings(SETTINGS)
    api_key = settings.get('api_key', '')
    try:
        with open(join(expanduser('~'), '.wakatime.conf')) as old_file:
            for line in old_file:
                line = line.split('=', 1)
                if line[0] == 'api_key':
                    api_key = line[1].strip()
    except IOError:
        pass
    settings.set('api_key', api_key)
    sublime.save_settings(SETTINGS)
    try:
        os.remove(join(expanduser('~'), '.wakatime.conf'))
    except:
        pass
convert_config_to_sublime_settings()


# Prompt for api key if not set in WakaTime.sublime-settings
def check_api_key():
    settings = sublime.load_settings(SETTINGS)
    api_key = settings.get('api_key', None)
    if not api_key:
        def got_key(text):
            if text:
                settings.set('api_key', str(api_key))
                sublime.save_settings(SETTINGS)
        sublime.active_window().show_input_panel('Enter your WakaTi.me api key:', '', got_key, None, None)
check_api_key()


def python_binary():
    python = 'python'
    if platform.system() == 'Windows':
        python = 'pythonw'
        try:
            Popen([python, '--version'])
        except:
            for path in glob.iglob('/python*'):
                if exists(realpath(join(path, 'pythonw.exe'))):
                    python = realpath(join(path, 'pythonw'))
                    break
    return python


def api(targetFile, timestamp, isWrite=False, endtime=0):
    global LAST_ACTION, LAST_USAGE, LAST_FILE
    if not targetFile:
        targetFile = LAST_FILE
    if targetFile:
        cmd = [python_binary(), API_CLIENT,
            '--file', targetFile,
            '--time', str('%f' % timestamp),
            '--plugin', 'sublime-wakatime/%s' % __version__,
            #'--verbose',
        ]
        api_key = sublime.load_settings(SETTINGS).get('api_key', None)
        if api_key:
            cmd.extend(['--key', str(api_key)])
        if isWrite:
            cmd.append('--write')
        if endtime:
            cmd.extend(['--endtime', str('%f' % endtime)])
        #print(cmd)
        if platform.system() == 'Windows':
            Popen(cmd, shell=False)
        else:
            with open(join(expanduser('~'), '.wakatime.log'), 'a') as stderr:
                Popen(cmd, stderr=stderr)
        LAST_ACTION = timestamp
        if endtime and endtime > LAST_ACTION:
            LAST_ACTION = endtime
        LAST_FILE = targetFile
        LAST_USAGE = LAST_ACTION
    else:
        LAST_USAGE = timestamp


def away(now):
    duration = now - LAST_USAGE
    minutes = ''
    units = 'second'
    if duration >= 60:
        duration = int(duration / 60)
        units = 'minute'
        if duration >= 60:
            remainder = duration % 60
            if remainder > 0:
                minutes = ' and %d minute' % remainder
            if remainder > 1:
                minutes = minutes + 's'
            duration = int(duration / 60)
            units = 'hour'
    if duration > 1:
        units = units + 's'
    return sublime\
        .ok_cancel_dialog("You were away %d %s%s. Add time to current file?"\
        % (duration, units, minutes), 'Yes, log this time')


def enough_time_passed(now):
    if now - LAST_ACTION > ACTION_FREQUENCY * 60:
        return True
    return False


def should_prompt_user(now):
    if not sublime.load_settings(SETTINGS).get('prompt_after_away', False):
        return False
    if not LAST_USAGE:
        return False
    duration = now - LAST_USAGE
    if duration > AWAY_MINUTES * 60:
        return True
    return False


def handle_write_action(view):
    global LAST_USAGE, BUSY
    BUSY = True
    targetFile = view.file_name()
    now = time.time()
    if enough_time_passed(now) or (LAST_FILE and targetFile != LAST_FILE):
        if should_prompt_user(now):
            if away(now):
                api(targetFile, now, endtime=LAST_ACTION, isWrite=True)
            else:
                api(targetFile, now, isWrite=True)
        else:
            api(targetFile, now, endtime=LAST_ACTION, isWrite=True)
    else:
        api(targetFile, now, isWrite=True)
    BUSY = False


def handle_normal_action(view):
    global LAST_USAGE, BUSY
    BUSY = True
    targetFile = view.file_name()
    now = time.time()
    if enough_time_passed(now) or (LAST_FILE and targetFile != LAST_FILE):
        if should_prompt_user(now):
            if away(now):
                api(targetFile, now, endtime=LAST_ACTION)
            else:
                api(targetFile, now)
        else:
            api(targetFile, now, endtime=LAST_ACTION)
    else:
        LAST_USAGE = now
    BUSY = False


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        if view.file_name():
            #print(['saved', view.file_name()])
            handle_write_action(view)

    def on_activated(self, view):
        if view.file_name() and not BUSY:
            #print(['activated', view.file_name()])
            handle_normal_action(view)

    def on_modified(self, view):
        if view.file_name() and not BUSY:
            #print(['modified', view.file_name()])
            handle_normal_action(view)

