""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""

__version__ = '3.0.6'

import sublime
import sublime_plugin

import glob
import os
import platform
import sys
import time
import threading
import uuid
from os.path import expanduser, dirname, basename, realpath, isfile, join, exists

# globals
ACTION_FREQUENCY = 2
ST_VERSION = int(sublime.version())
PLUGIN_DIR = dirname(realpath(__file__))
API_CLIENT = '%s/packages/wakatime/wakatime-cli.py' % PLUGIN_DIR
SETTINGS_FILE = 'WakaTime.sublime-settings'
SETTINGS = {}
LAST_ACTION = {
    'time': 0,
    'file': None,
    'is_write': False,
}
HAS_SSL = False
LOCK = threading.RLock()

# add wakatime package to path
sys.path.insert(0, join(PLUGIN_DIR, 'packages', 'wakatime'))

from wakatime import parseConfigFile

# check if we have SSL support
try:
    import ssl
    import socket
    socket.ssl
    HAS_SSL = True
except (ImportError, AttributeError):
    from subprocess import Popen

if HAS_SSL:
    # import wakatime package so we can use built-in python
    import wakatime


def createConfigFile():
    """Creates the .wakatime.cfg INI file in $HOME directory, if it does
    not already exist.
    """
    configFile = os.path.join(os.path.expanduser('~'), '.wakatime.cfg')
    try:
        with open(configFile) as fh:
            pass
    except IOError:
        try:
            with open(configFile, 'w') as fh:
                fh.write("[settings]\n")
                fh.write("debug = false\n")
                fh.write("hidefilenames = false\n")
        except IOError:
            pass


def prompt_api_key():
    global SETTINGS

    createConfigFile()

    default_key = ''
    configs = parseConfigFile()
    if configs is not None:
        if configs.has_option('settings', 'api_key'):
            default_key = configs.get('settings', 'api_key')

    if SETTINGS.get('api_key'):
        return True
    else:
        def got_key(text):
            if text:
                SETTINGS.set('api_key', str(text))
                sublime.save_settings(SETTINGS_FILE)
        window = sublime.active_window()
        if window:
            window.show_input_panel('[WakaTime] Enter your wakatime.com api key:', default_key, got_key, None, None)
            return True
        else:
            print('[WakaTime] Error: Could not prompt for api key because no window found.')
    return False


def python_binary():
    if platform.system() == 'Windows':
        try:
            Popen(['pythonw', '--version'])
            return 'pythonw'
        except:
            for path in glob.iglob('/python*'):
                if exists(realpath(join(path, 'pythonw.exe'))):
                    return realpath(join(path, 'pythonw'))
            return None
    return 'python'


def enough_time_passed(now, last_time):
    if now - last_time > ACTION_FREQUENCY * 60:
        return True
    return False


def find_project_name_from_folders(folders):
    for folder in folders:
        for file_name in os.listdir(folder):
            if file_name.endswith('.sublime-project'):
                return file_name.replace('.sublime-project', '', 1)
    return None


def handle_action(view, is_write=False):
    global LOCK, LAST_ACTION
    with LOCK:
        target_file = view.file_name()
        if target_file:
            project = view.window().project_file_name() if hasattr(view.window(), 'project_file_name') else None
            if project:
                project = basename(project).replace('.sublime-project', '', 1)
            thread = SendActionThread(target_file, is_write=is_write, project=project, folders=view.window().folders())
            thread.start()
            LAST_ACTION = {
                'file': target_file,
                'time': time.time(),
                'is_write': is_write,
            }


class SendActionThread(threading.Thread):

    def __init__(self, target_file, is_write=False, project=None, folders=None, force=False):
        threading.Thread.__init__(self)
        self.target_file = target_file
        self.is_write = is_write
        self.project = project
        self.folders = folders
        self.force = force
        self.debug = SETTINGS.get('debug')
        self.api_key = SETTINGS.get('api_key', '')
        self.ignore = SETTINGS.get('ignore', [])
        self.last_action = LAST_ACTION

    def run(self):
        if self.target_file:
            self.timestamp = time.time()
            if self.force or (self.is_write and not self.last_action['is_write']) or self.target_file != self.last_action['file'] or enough_time_passed(self.timestamp, self.last_action['time']):
                self.send()

    def send(self):
        if not self.api_key:
            print('[WakaTime] Error: missing api key.')
            return
        ua = 'sublime/%d sublime-wakatime/%s' % (ST_VERSION, __version__)
        cmd = [
            API_CLIENT,
            '--file', self.target_file,
            '--time', str('%f' % self.timestamp),
            '--plugin', ua,
            '--key', str(bytes.decode(self.api_key.encode('utf8'))),
        ]
        if self.is_write:
            cmd.append('--write')
        if self.project:
            cmd.extend(['--project', self.project])
        elif self.folders:
            project_name = find_project_name_from_folders(self.folders)
            if project_name:
                cmd.extend(['--project', project_name])
        for pattern in self.ignore:
            cmd.extend(['--ignore', pattern])
        if self.debug:
            cmd.append('--verbose')
        if HAS_SSL:
            if self.debug:
                print('[WakaTime] %s' % ' '.join(cmd))
            code = wakatime.main(cmd)
            if code != 0:
                print('[WakaTime] Error: Response code %d from wakatime package.' % code)
        else:
            python = python_binary()
            if python:
                cmd.insert(0, python)
                if self.debug:
                    print('[WakaTime] %s' % ' '.join(cmd))
                if platform.system() == 'Windows':
                    Popen(cmd, shell=False)
                else:
                    with open(join(expanduser('~'), '.wakatime.log'), 'a') as stderr:
                        Popen(cmd, stderr=stderr)
            else:
                print('[WakaTime] Error: Unable to find python binary.')


def plugin_loaded():
    global SETTINGS
    print('[WakaTime] Initializing WakaTime plugin v%s' % __version__)

    if not HAS_SSL:
        python = python_binary()
        if not python:
            sublime.error_message("Unable to find Python binary!\nWakaTime needs Python to work correctly.\n\nGo to https://www.python.org/downloads")
            return

    SETTINGS = sublime.load_settings(SETTINGS_FILE)
    after_loaded()


def after_loaded():
    if not prompt_api_key():
        sublime.set_timeout(after_loaded, 500)


# need to call plugin_loaded because only ST3 will auto-call it
if ST_VERSION < 3000:
    plugin_loaded()


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        handle_action(view, is_write=True)

    def on_activated(self, view):
        handle_action(view)

    def on_modified(self, view):
        handle_action(view)
