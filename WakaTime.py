# -*- coding: utf-8 -*-
""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""


__version__ = '10.0.0'


import sublime
import sublime_plugin

import json
import os
import platform
import re
import subprocess
import sys
import time
import threading
import traceback
import webbrowser
import ssl
import shutil
from subprocess import STDOUT, PIPE
from zipfile import ZipFile
try:
    import Queue as queue  # py2
except ImportError:
    import queue  # py3
try:
    import ConfigParser as configparser
except ImportError:
    import configparser
try:
    from urllib2 import urlretrieve
except ImportError:
    from urllib.request import urlretrieve


is_win = platform.system() == 'Windows'


if platform.system() == 'Windows':
    RESOURCES_FOLDER = os.path.join(os.getenv('APPDATA'), 'WakaTime')
else:
    RESOURCES_FOLDER = os.path.join(os.path.expanduser('~'), '.wakatime')
if not os.path.exists(RESOURCES_FOLDER):
    os.makedirs(RESOURCES_FOLDER)


class Popen(subprocess.Popen):
    """Patched Popen to prevent opening cmd window on Windows platform."""

    def __init__(self, *args, **kwargs):
        startupinfo = kwargs.get('startupinfo')
        if is_win or True:
            try:
                startupinfo = startupinfo or subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except AttributeError:
                pass
        kwargs['startupinfo'] = startupinfo
        super(Popen, self).__init__(*args, **kwargs)


# globals
ST_VERSION = int(sublime.version())
API_CLIENT = os.path.join(RESOURCES_FOLDER, 'wakatime-cli', 'wakatime-cli' + ('.exe' if is_win else ''))
S3_HOST = 'https://wakatime-cli.s3-us-west-2.amazonaws.com'
SETTINGS_FILE = 'WakaTime.sublime-settings'
SETTINGS = {}
LAST_HEARTBEAT = {
    'time': 0,
    'file': None,
    'is_write': False,
}
LAST_HEARTBEAT_SENT_AT = 0
LAST_FETCH_TODAY_CODING_TIME = 0
FETCH_TODAY_DEBOUNCE_COUNTER = 0
FETCH_TODAY_DEBOUNCE_SECONDS = 60
HEARTBEATS = queue.Queue()
HEARTBEAT_FREQUENCY = 2  # minutes between logging heartbeat when editing same file
SEND_BUFFER_SECONDS = 30  # seconds between sending buffered heartbeats to API


# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


class ApiKey(object):
    _key = None

    def _configFile(self):
        home = os.environ.get('WAKATIME_HOME')
        if home:
            return os.path.join(os.path.expanduser(home), '.wakatime.cfg')

        return os.path.join(os.path.expanduser('~'), '.wakatime.cfg')

    def _parseConfigFile(self):
        """Returns a configparser.SafeConfigParser instance with configs
        read from the config file. Default location of the config file is
        at ~/.wakatime.cfg.
        """

        configFile = self._configFile()

        configs = configparser.SafeConfigParser()
        try:
            with open(configFile, 'r', encoding='utf-8') as fh:
                try:
                    configs.readfp(fh)
                    return configs
                except configparser.Error:
                    log(ERROR, traceback.format_exc())
                    return None
        except IOError:
            log(DEBUG, "Error: Could not read from config file {0}\n".format(configFile))
            return None

    def read(self):
        if self._key:
            return self._key

        key = SETTINGS.get('api_key')
        if key:
            self._key = key
            return self._key

        try:
            configs = self._parseConfigFile()
            if configs:
                if configs.has_option('settings', 'api_key'):
                    key = configs.get('settings', 'api_key')
                    if key:
                        self._key = key
                        return self._key
        except:
            pass

        return self._key

    def write(self, key):
        global SETTINGS
        self._key = key
        SETTINGS.set('api_key', str(key))
        sublime.save_settings(SETTINGS_FILE)


APIKEY = ApiKey()


def set_timeout(callback, seconds):
    """Runs the callback after the given seconds delay.

    If this is Sublime Text 3, runs the callback on an alternate thread. If this
    is Sublime Text 2, runs the callback in the main thread.
    """

    milliseconds = int(seconds * 1000)
    try:
        sublime.set_timeout_async(callback, milliseconds)
    except AttributeError:
        sublime.set_timeout(callback, milliseconds)


def log(lvl, message, *args, **kwargs):
    try:
        if lvl == DEBUG and not SETTINGS.get('debug'):
            return
        msg = message
        if len(args) > 0:
            msg = message.format(*args)
        elif len(kwargs) > 0:
            msg = message.format(**kwargs)
        try:
            print('[WakaTime] [{lvl}] {msg}'.format(lvl=lvl, msg=msg))
        except UnicodeDecodeError:
            print('[WakaTime] [{lvl}] {msg}'.format(lvl=lvl, msg=msg))
    except RuntimeError:
        set_timeout(lambda: log(lvl, message, *args, **kwargs), 0)


def update_status_bar(status=None, debounced=False, msg=None):
    """Updates the status bar."""
    global LAST_FETCH_TODAY_CODING_TIME, FETCH_TODAY_DEBOUNCE_COUNTER

    try:
        if not msg and SETTINGS.get('status_bar_message') is not False and SETTINGS.get('status_bar_enabled'):
            if SETTINGS.get('status_bar_coding_activity') and status == 'OK':
                if debounced:
                    FETCH_TODAY_DEBOUNCE_COUNTER -= 1
                if debounced or not LAST_FETCH_TODAY_CODING_TIME:
                    now = int(time.time())
                    if LAST_FETCH_TODAY_CODING_TIME and (FETCH_TODAY_DEBOUNCE_COUNTER > 0 or LAST_FETCH_TODAY_CODING_TIME > now - FETCH_TODAY_DEBOUNCE_SECONDS):
                        return
                    LAST_FETCH_TODAY_CODING_TIME = now
                    FetchStatusBarCodingTime().start()
                    return
                else:
                    FETCH_TODAY_DEBOUNCE_COUNTER += 1
                    set_timeout(lambda: update_status_bar(status, debounced=True), FETCH_TODAY_DEBOUNCE_SECONDS)
                    return
            else:
                msg = 'WakaTime: {status}'.format(status=status)

        if msg:
            active_window = sublime.active_window()
            if active_window:
                for view in active_window.views():
                    view.set_status('wakatime', msg)

    except RuntimeError:
        set_timeout(lambda: update_status_bar(status=status, debounced=debounced, msg=msg), 0)


class FetchStatusBarCodingTime(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

        self.debug = SETTINGS.get('debug')
        self.api_key = APIKEY.read() or ''
        self.proxy = SETTINGS.get('proxy')

    def run(self):
        if not self.api_key:
            log(DEBUG, 'Missing WakaTime API key.')
            return
        if not isCliInstalled():
            return

        ua = 'sublime/%d sublime-wakatime/%s' % (ST_VERSION, __version__)
        cmd = [
            API_CLIENT,
            '--today',
            '--key', str(bytes.decode(self.api_key.encode('utf8'))),
            '--plugin', ua,
        ]
        if self.debug:
            cmd.append('--verbose')
        if self.proxy:
            cmd.extend(['--proxy', self.proxy])

        log(DEBUG, ' '.join(obfuscate_apikey(cmd)))
        try:
            process = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            output, _err = process.communicate()
            retcode = process.poll()
            if not retcode and output:
                msg = 'Today: {output}'.format(output=output.decode('utf-8'))
                update_status_bar(msg=msg)
            else:
                log(DEBUG, 'wakatime-core today exited with status: {0}'.format(retcode))
                if output:
                    log(DEBUG, 'wakatime-core today output: {0}'.format(output))
        except:
            pass


def prompt_api_key():
    if APIKEY.read():
        return True

    window = sublime.active_window()
    if window:
        def got_key(text):
            if text:
                APIKEY.write(text)
        window.show_input_panel('[WakaTime] Enter your wakatime.com api key:', '', got_key, None, None)
        return True
    else:
        log(ERROR, 'Could not prompt for api key because no window found.')
        return False


def obfuscate_apikey(command_list):
    cmd = list(command_list)
    apikey_index = None
    for num in range(len(cmd)):
        if cmd[num] == '--key':
            apikey_index = num + 1
            break
    if apikey_index is not None and apikey_index < len(cmd):
        cmd[apikey_index] = 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX' + cmd[apikey_index][-4:]
    return cmd


def enough_time_passed(now, is_write):
    if now - LAST_HEARTBEAT['time'] > HEARTBEAT_FREQUENCY * 60:
        return True
    if is_write and now - LAST_HEARTBEAT['time'] > 2:
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


def handle_activity(view, is_write=False):
    window = view.window()
    if window is not None:
        entity = view.file_name()
        if entity:
            timestamp = time.time()
            last_file = LAST_HEARTBEAT['file']
            if entity != last_file or enough_time_passed(timestamp, is_write):
                project = window.project_data() if hasattr(window, 'project_data') else None
                folders = window.folders()
                append_heartbeat(entity, timestamp, is_write, view, project, folders)


def append_heartbeat(entity, timestamp, is_write, view, project, folders):
    global LAST_HEARTBEAT

    # add this heartbeat to queue
    heartbeat = {
        'entity': entity,
        'timestamp': timestamp,
        'is_write': is_write,
        'cursorpos': view.sel()[0].begin() if view.sel() else None,
        'project': project,
        'folders': folders,
    }
    HEARTBEATS.put_nowait(heartbeat)

    # make this heartbeat the LAST_HEARTBEAT
    LAST_HEARTBEAT = {
        'file': entity,
        'time': timestamp,
        'is_write': is_write,
    }

    # process the queue of heartbeats in the future
    set_timeout(lambda: process_queue(timestamp), SEND_BUFFER_SECONDS)


def process_queue(timestamp):
    global LAST_HEARTBEAT_SENT_AT

    if not isCliInstalled():
        return

    # Prevent sending heartbeats more often than SEND_BUFFER_SECONDS
    now = int(time.time())
    if timestamp != LAST_HEARTBEAT['time'] and LAST_HEARTBEAT_SENT_AT > now - SEND_BUFFER_SECONDS:
        return
    LAST_HEARTBEAT_SENT_AT = now

    try:
        heartbeat = HEARTBEATS.get_nowait()
    except queue.Empty:
        return

    has_extra_heartbeats = False
    extra_heartbeats = []
    try:
        while True:
            extra_heartbeats.append(HEARTBEATS.get_nowait())
            has_extra_heartbeats = True
    except queue.Empty:
        pass

    thread = SendHeartbeatsThread(heartbeat)
    if has_extra_heartbeats:
        thread.add_extra_heartbeats(extra_heartbeats)
    thread.start()


class SendHeartbeatsThread(threading.Thread):
    """Non-blocking thread for sending heartbeats to api.
    """

    def __init__(self, heartbeat):
        threading.Thread.__init__(self)

        self.debug = SETTINGS.get('debug')
        self.api_key = APIKEY.read() or ''
        self.ignore = SETTINGS.get('ignore', [])
        self.include = SETTINGS.get('include', [])
        self.hidefilenames = SETTINGS.get('hidefilenames')
        self.proxy = SETTINGS.get('proxy')

        self.heartbeat = heartbeat
        self.has_extra_heartbeats = False

    def add_extra_heartbeats(self, extra_heartbeats):
        self.has_extra_heartbeats = True
        self.extra_heartbeats = extra_heartbeats

    def run(self):
        """Running in background thread."""

        self.send_heartbeats()

    def build_heartbeat(self, entity=None, timestamp=None, is_write=None,
                        cursorpos=None, project=None, folders=None):
        """Returns a dict for passing to wakatime-cli as arguments."""

        heartbeat = {
            'entity': entity,
            'timestamp': timestamp,
            'is_write': is_write,
        }

        if project and project.get('name'):
            heartbeat['alternate_project'] = project.get('name')
        elif folders:
            project_name = find_project_from_folders(folders, entity)
            if project_name:
                heartbeat['alternate_project'] = project_name

        if cursorpos is not None:
            heartbeat['cursorpos'] = '{0}'.format(cursorpos)

        return heartbeat

    def send_heartbeats(self):
        heartbeat = self.build_heartbeat(**self.heartbeat)
        ua = 'sublime/%d sublime-wakatime/%s' % (ST_VERSION, __version__)
        cmd = [
            API_CLIENT,
            '--entity', heartbeat['entity'],
            '--time', str('%f' % heartbeat['timestamp']),
            '--plugin', ua,
        ]
        if self.api_key:
            cmd.extend(['--key', str(bytes.decode(self.api_key.encode('utf8')))])
        if heartbeat['is_write']:
            cmd.append('--write')
        if heartbeat.get('alternate_project'):
            cmd.extend(['--alternate-project', heartbeat['alternate_project']])
        if heartbeat.get('cursorpos') is not None:
            cmd.extend(['--cursorpos', heartbeat['cursorpos']])
        for pattern in self.ignore:
            cmd.extend(['--exclude', pattern])
        for pattern in self.include:
            cmd.extend(['--include', pattern])
        if self.debug:
            cmd.append('--verbose')
        if self.hidefilenames:
            cmd.append('--hidefilenames')
        if self.proxy:
            cmd.extend(['--proxy', self.proxy])
        if self.has_extra_heartbeats:
            cmd.append('--extra-heartbeats')
            stdin = PIPE
            extra_heartbeats = json.dumps([self.build_heartbeat(**x) for x in self.extra_heartbeats])
            inp = "{0}\n".format(extra_heartbeats).encode('utf-8')
        else:
            extra_heartbeats = None
            stdin = None
            inp = None

        log(DEBUG, ' '.join(obfuscate_apikey(cmd)))
        try:
            process = Popen(cmd, stdin=stdin, stdout=PIPE, stderr=STDOUT)
            output, _err = process.communicate(input=inp)
            retcode = process.poll()
            if (not retcode or retcode == 102) and not output:
                self.sent()
            else:
                update_status_bar('Error')
            if retcode:
                log(DEBUG if retcode == 102 else ERROR, 'wakatime-core exited with status: {0}'.format(retcode))
            if output:
                log(ERROR, 'wakatime-core output: {0}'.format(output))
        except:
            log(ERROR, sys.exc_info()[1])
            update_status_bar('Error')

    def sent(self):
        update_status_bar('OK')


def plugin_loaded():
    global SETTINGS
    SETTINGS = sublime.load_settings(SETTINGS_FILE)

    log(INFO, 'Initializing WakaTime plugin v%s' % __version__)
    update_status_bar('Initializing...')

    if not isCliLatest():
        thread = DownloadCLI()
        thread.start()

    log(INFO, 'Finished initializing WakaTime v%s' % __version__)

    after_loaded()


def after_loaded():
    if not prompt_api_key():
        set_timeout(after_loaded, 0.5)
    update_status_bar('OK')


# need to call plugin_loaded because only ST3 will auto-call it
if ST_VERSION < 3000:
    plugin_loaded()


class WakatimeListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        handle_activity(view, is_write=True)

    def on_selection_modified(self, view):
        if is_view_active(view):
            handle_activity(view)

    def on_modified(self, view):
        if is_view_active(view):
            handle_activity(view)


class WakatimeDashboardCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        webbrowser.open_new_tab('https://wakatime.com/dashboard')


class DownloadCLI(threading.Thread):
    """Non-blocking thread for downloading latest wakatime-cli from GitHub.
    """

    def run(self):
        log(INFO, 'Downloading wakatime-cli...')

        try:
            shutil.rmtree(os.path.join(RESOURCES_FOLDER, 'wakatime-cli'))
        except:
            pass

        try:
            url = self._getCliUrl()
            zip_file = os.path.join(RESOURCES_FOLDER, 'wakatime-cli.zip')
            download(url, zip_file)

            log(INFO, 'Extracting wakatime-cli...')
            with ZipFile(zip_file) as zf:
                zf.extractall(RESOURCES_FOLDER)

            try:
                shutil.rmtree(os.path.join(RESOURCES_FOLDER, 'wakatime-cli.zip'))
            except:
                pass
        except:
            log(DEBUG, traceback.format_exc())

        log(INFO, 'Finished extracting wakatime-cli.')

    def _getCliUrl(self):
        os = platform.system().lower().replace('darwin', 'mac')
        arch = '64' if sys.maxsize > 2**32 else '32'
        return '{host}/{os}-x86-{arch}/wakatime-cli.zip'.format(
            host=S3_HOST,
            os=os,
            arch=arch,
        )


def isCliInstalled():
    return os.path.exists(API_CLIENT)


def isCliLatest():
    if not isCliInstalled():
        return False

    args = [API_CLIENT, '--version']
    stdout, stderr = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
    stdout = (stdout or b'') + (stderr or b'')
    localVer = extractVersion(stdout.decode('utf-8'))
    if not localVer:
        return False

    log(INFO, 'Current wakatime-cli version is %s' % localVer)
    log(INFO, 'Checking for updates to wakatime-cli...')

    remoteVer = getLatestCliVersion()

    if not remoteVer:
        return True

    if remoteVer == localVer:
        log(INFO, 'wakatime-cli is up to date.')
        return True

    log(INFO, 'Found an updated wakatime-cli v%s' % remoteVer)
    return False


def getLatestCliVersion():
    url = getCliVersionUrl()
    try:
        localFile = os.path.join(RESOURCES_FOLDER, 'current_version.txt')
        download(url, localFile)
        ver = None
        with open(localFile) as fh:
            ver = extractVersion(fh.read())
        try:
            shutil.rmtree(localFile)
        except:
            pass
        return ver
    except:
        return None


def getCliVersionUrl():
    os = platform.system().lower().replace('darwin', 'mac')
    arch = '64' if sys.maxsize > 2**32 else '32'
    return '{host}/{os}-x86-{arch}/current_version.txt'.format(
        host=S3_HOST,
        os=os,
        arch=arch,
    )


def extractVersion(text):
    log(DEBUG, 'extracting version.')
    pattern = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)")
    match = pattern.search(text)
    if match:
        return match.group(1)
    return None


def download(url, filePath):
    try:
        urlretrieve(url, filePath)
    except IOError:
        ssl._create_default_https_context = ssl._create_unverified_context
        urlretrieve(url, filePath)
