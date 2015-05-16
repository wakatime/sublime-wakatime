""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""


__version__ = '4.0.6'


import sublime
import sublime_plugin

import glob
import os
import platform
import sys
import time
import threading
import webbrowser
from datetime import datetime
from subprocess import Popen


# globals
HEARTBEAT_FREQUENCY = 2
ST_VERSION = int(sublime.version())
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
API_CLIENT = os.path.join(PLUGIN_DIR, 'packages', 'wakatime', 'cli.py')
SETTINGS_FILE = 'WakaTime.sublime-settings'
SETTINGS = {}
LAST_HEARTBEAT = {
    'time': 0,
    'file': None,
    'is_write': False,
}
LOCK = threading.RLock()
PYTHON_LOCATION = None


# add wakatime package to path
sys.path.insert(0, os.path.join(PLUGIN_DIR, 'packages'))
try:
    from wakatime.base import parseConfigFile
except ImportError:
    pass


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
    try:
        configs = parseConfigFile()
        if configs is not None:
            if configs.has_option('settings', 'api_key'):
                default_key = configs.get('settings', 'api_key')
    except:
        pass

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
    global PYTHON_LOCATION
    if PYTHON_LOCATION is not None:
        return PYTHON_LOCATION
    paths = [
        "pythonw",
        "python",
        "/usr/local/bin/python",
        "/usr/bin/python",
    ]
    for path in paths:
        try:
            Popen([path, '--version'])
            PYTHON_LOCATION = path
            return path
        except:
            pass
    for path in glob.iglob('/python*'):
        path = os.path.realpath(os.path.join(path, 'pythonw'))
        try:
            Popen([path, '--version'])
            PYTHON_LOCATION = path
            return path
        except:
            pass
    return None


def obfuscate_apikey(command_list):
    cmd = list(command_list)
    apikey_index = None
    for num in range(len(cmd)):
        if cmd[num] == '--key':
            apikey_index = num + 1
            break
    if apikey_index is not None and apikey_index < len(cmd):
        cmd[apikey_index] = '********-****-****-****-********' + cmd[apikey_index][-4:]
    return cmd


def enough_time_passed(now, last_heartbeat, is_write):
    if now - last_heartbeat['time'] > HEARTBEAT_FREQUENCY * 60:
        return True
    if is_write and now - last_heartbeat['time'] > 2:
        return True
    return False


def find_folder_containing_file(folders, current_file):
    """Returns absolute path to folder containing the file.
    """

    parent_folder = None

    current_folder = current_file
    while True:
        for folder in folders:
            if os.path.realpath(os.path.dirname(current_folder)) == os.path.realpath(folder):
                parent_folder = folder
                break
        if parent_folder is not None:
            break
        if not current_folder or os.path.dirname(current_folder) == current_folder:
            break
        current_folder = os.path.dirname(current_folder)

    return parent_folder


def find_project_from_folders(folders, current_file):
    """Find project name from open folders.
    """

    folder = find_folder_containing_file(folders, current_file)
    return os.path.basename(folder) if folder else None


def is_view_active(view):
    if view:
        active_window = sublime.active_window()
        if active_window:
            active_view = active_window.active_view()
            if active_view:
                return active_view.buffer_id() == view.buffer_id()
    return False


def handle_heartbeat(view, is_write=False):
    window = view.window()
    if window is not None:
        target_file = view.file_name()
        project = window.project_data() if hasattr(window, 'project_data') else None
        folders = window.folders()
        thread = SendHeartbeatThread(target_file, view, is_write=is_write, project=project, folders=folders)
        thread.start()


class SendHeartbeatThread(threading.Thread):

    def __init__(self, target_file, view, is_write=False, project=None, folders=None, force=False):
        threading.Thread.__init__(self)
        self.lock = LOCK
        self.target_file = target_file
        self.is_write = is_write
        self.project = project
        self.folders = folders
        self.force = force
        self.debug = SETTINGS.get('debug')
        self.api_key = SETTINGS.get('api_key', '')
        self.ignore = SETTINGS.get('ignore', [])
        self.last_heartbeat = LAST_HEARTBEAT.copy()
        self.cursorpos = view.sel()[0].begin() if view.sel() else None
        self.view = view

    def run(self):
        with self.lock:
            if self.target_file:
                self.timestamp = time.time()
                if self.force or self.target_file != self.last_heartbeat['file'] or enough_time_passed(self.timestamp, self.last_heartbeat, self.is_write):
                    self.send_heartbeat()

    def send_heartbeat(self):
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
        if self.project and self.project.get('name'):
            cmd.extend(['--alternate-project', self.project.get('name')])
        elif self.folders:
            project_name = find_project_from_folders(self.folders, self.target_file)
            if project_name:
                cmd.extend(['--alternate-project', project_name])
        if self.cursorpos is not None:
            cmd.extend(['--cursorpos', '{0}'.format(self.cursorpos)])
        for pattern in self.ignore:
            cmd.extend(['--ignore', pattern])
        if self.debug:
            cmd.append('--verbose')
        if python_binary():
            cmd.insert(0, python_binary())
            if self.debug:
                print('[WakaTime] %s' % ' '.join(obfuscate_apikey(cmd)))
            if platform.system() == 'Windows':
                Popen(cmd, shell=False)
            else:
                with open(os.path.join(os.path.expanduser('~'), '.wakatime.log'), 'a') as stderr:
                    Popen(cmd, stderr=stderr)
            self.sent()
        else:
            print('[WakaTime] Error: Unable to find python binary.')

    def sent(self):
        sublime.set_timeout(self.set_status_bar, 0)
        sublime.set_timeout(self.set_last_heartbeat, 0)

    def set_status_bar(self):
        if SETTINGS.get('status_bar_message'):
            self.view.set_status('wakatime', 'WakaTime active {0}'.format(datetime.now().strftime('%I:%M %p')))

    def set_last_heartbeat(self):
        global LAST_HEARTBEAT
        LAST_HEARTBEAT = {
            'file': self.target_file,
            'time': self.timestamp,
            'is_write': self.is_write,
        }


def plugin_loaded():
    global SETTINGS
    print('[WakaTime] Initializing WakaTime plugin v%s' % __version__)

    if not python_binary():
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
        handle_heartbeat(view, is_write=True)

    def on_selection_modified(self, view):
        if is_view_active(view):
            handle_heartbeat(view)

    def on_modified(self, view):
        if is_view_active(view):
            handle_heartbeat(view)


class WakatimeDashboardCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        webbrowser.open_new_tab('https://wakatime.com/dashboard')
