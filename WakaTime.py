# -*- coding: utf-8 -*-
""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""


__version__ = '9.1.2'


import sublime
import sublime_plugin

import contextlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import threading
import traceback
import urllib
import webbrowser
from subprocess import STDOUT, PIPE
from zipfile import ZipFile
try:
    import _winreg as winreg  # py2
except ImportError:
    try:
        import winreg  # py3
    except ImportError:
        winreg = None
try:
    import Queue as queue  # py2
except ImportError:
    import queue  # py3


is_py2 = (sys.version_info[0] == 2)
is_py3 = (sys.version_info[0] == 3)
is_win = platform.system() == 'Windows'


if is_py2:
    def u(text):
        if text is None:
            return None
        if isinstance(text, unicode):
            return text
        try:
            return text.decode('utf-8')
        except:
            try:
                return text.decode(sys.getdefaultencoding())
            except:
                try:
                    return unicode(text)
                except:
                    try:
                        return text.decode('utf-8', 'replace')
                    except:
                        try:
                            return unicode(str(text))
                        except:
                            return unicode('')

elif is_py3:
    def u(text):
        if text is None:
            return None
        if isinstance(text, bytes):
            try:
                return text.decode('utf-8')
            except:
                try:
                    return text.decode(sys.getdefaultencoding())
                except:
                    pass
        try:
            return str(text)
        except:
            return text.decode('utf-8', 'replace')

else:
    raise Exception('Unsupported Python version: {0}.{1}.{2}'.format(
        sys.version_info[0],
        sys.version_info[1],
        sys.version_info[2],
    ))


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
PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
API_CLIENT = os.path.join(PLUGIN_DIR, 'packages', 'wakatime', 'cli.py')
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
PYTHON_LOCATION = None
HEARTBEATS = queue.Queue()
HEARTBEAT_FREQUENCY = 2  # minutes between logging heartbeat when editing same file
SEND_BUFFER_SECONDS = 30  # seconds between sending buffered heartbeats to API


# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


# add wakatime package to path
sys.path.insert(0, os.path.join(PLUGIN_DIR, 'packages'))
try:
    from wakatime.configs import parseConfigFile
except ImportError:
    def parseConfigFile():
        return None


class ApiKey(object):
    _key = None

    def read(self):
        if self._key:
            return self._key

        key = SETTINGS.get('api_key')
        if key:
            self._key = key
            return self._key

        try:
            configs = parseConfigFile()
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
            print(u('[WakaTime] [{lvl}] {msg}').format(lvl=lvl, msg=u(msg)))
    except RuntimeError:
        set_timeout(lambda: log(lvl, message, *args, **kwargs), 0)


def resources_folder():
    if is_win:
        return os.path.join(os.getenv('APPDATA'), 'WakaTime')
    else:
        return os.path.join(os.path.expanduser('~'), '.wakatime')


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
        self.python_binary = SETTINGS.get('python_binary')

    def run(self):
        if not self.api_key:
            log(DEBUG, 'Missing WakaTime API key.')
            return

        python = self.python_binary
        if not python or not python.strip():
            python = python_binary()
        if not python:
            log(DEBUG, 'Missing Python.')
            return

        ua = 'sublime/%d sublime-wakatime/%s' % (ST_VERSION, __version__)
        cmd = [
            python,
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
            output, err = process.communicate()
            output = u(output)
            retcode = process.poll()
            if not retcode and output:
                msg = 'Today: {output}'.format(output=output)
                update_status_bar(msg=msg)
            else:
                log(DEBUG, 'wakatime-core today exited with status: {0}'.format(retcode))
                if output:
                    log(DEBUG, u('wakatime-core today output: {0}').format(output))
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


def python_binary():
    if PYTHON_LOCATION is not None:
        return PYTHON_LOCATION

    # look for python in PATH and common install locations
    paths = [
        os.path.join(resources_folder(), 'python'),
        None,
        '/',
        '/usr/local/bin/',
        '/usr/bin/',
    ]

    if is_win and os.getenv('LOCALAPPDATA'):
        appdata = os.getenv('LOCALAPPDATA')
        ver = 39
        while ver >= 27:
            if ver >= 30 and ver <= 33:
                ver -= 1
                continue
            paths.append('\\python{ver}\\'.format(ver=ver))
            paths.append('\\Python{ver}\\'.format(ver=ver))
            paths.append('{appdata}\\Programs\Python{ver}\\'.format(appdata=appdata, ver=ver))
            paths.append('{appdata}\\Programs\Python{ver}-32\\'.format(appdata=appdata, ver=ver))
            paths.append('{appdata}\\Programs\Python{ver}-64\\'.format(appdata=appdata, ver=ver))
            ver -= 1

    for path in paths:
        path = find_python_in_folder(path)
        if path is not None:
            set_python_binary_location(path)
            return path

    # look for python in windows registry
    path = find_python_from_registry(r'SOFTWARE\Python\PythonCore')
    if path is not None:
        set_python_binary_location(path)
        return path
    path = find_python_from_registry(r'SOFTWARE\Wow6432Node\Python\PythonCore')
    if path is not None:
        set_python_binary_location(path)
        return path

    return None


def set_python_binary_location(path):
    global PYTHON_LOCATION
    PYTHON_LOCATION = path
    log(DEBUG, 'Found Python at: {0}'.format(path))


def find_python_from_registry(location, reg=None):
    if not is_win or winreg is None:
        return None

    if reg is None:
        path = find_python_from_registry(location, reg=winreg.HKEY_CURRENT_USER)
        if path is None:
            path = find_python_from_registry(location, reg=winreg.HKEY_LOCAL_MACHINE)
        return path

    val = None
    sub_key = 'InstallPath'
    compiled = re.compile(r'^\d+\.\d+$')

    try:
        with winreg.OpenKey(reg, location) as handle:
            versions = []
            try:
                for index in range(1024):
                    version = winreg.EnumKey(handle, index)
                    try:
                        if compiled.search(version):
                            versions.append(version)
                    except re.error:
                        pass
            except EnvironmentError:
                pass
            versions.sort(reverse=True)
            for version in versions:
                try:
                    path = winreg.QueryValue(handle, version + '\\' + sub_key)
                    if path is not None:
                        path = find_python_in_folder(path)
                        if path is not None:
                            log(DEBUG, 'Found python from {reg}\\{key}\\{version}\\{sub_key}.'.format(
                                reg=reg,
                                key=location,
                                version=version,
                                sub_key=sub_key,
                            ))
                            return path
                except WindowsError:
                    log(DEBUG, 'Could not read registry value "{reg}\\{key}\\{version}\\{sub_key}".'.format(
                        reg=reg,
                        key=location,
                        version=version,
                        sub_key=sub_key,
                    ))
    except WindowsError:
        log(DEBUG, 'Could not read registry value "{reg}\\{key}".'.format(
            reg=reg,
            key=location,
        ))
    except:
        log(ERROR, 'Could not read registry value "{reg}\\{key}":\n{exc}'.format(
            reg=reg,
            key=location,
            exc=traceback.format_exc(),
        ))

    return val


def find_python_in_folder(folder, python3=True, headless=True):
    pattern = re.compile(r'\d+\.\d+')

    path = 'python'
    if folder:
        path = os.path.realpath(os.path.join(folder, 'python'))
    if python3:
        path = u(path) + u('3')
    elif headless:
        path = u(path) + u('w')
    log(DEBUG, u('Looking for Python at: {0}').format(u(path)))
    try:
        process = Popen([path, '--version'], stdout=PIPE, stderr=STDOUT)
        output, err = process.communicate()
        output = u(output).strip()
        retcode = process.poll()
        log(DEBUG, u('Python Version Output: {0}').format(output))
        if not retcode and pattern.search(output):
            return path
    except:
        log(DEBUG, u(sys.exc_info()[1]))

    if python3:
        path = find_python_in_folder(folder, python3=False, headless=headless)
        if path:
            return path
    elif headless:
        path = find_python_in_folder(folder, python3=python3, headless=False)
        if path:
            return path

    return None


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
        self.python_binary = SETTINGS.get('python_binary')

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
        python = self.python_binary
        if not python or not python.strip():
            python = python_binary()
        if python:
            heartbeat = self.build_heartbeat(**self.heartbeat)
            ua = 'sublime/%d sublime-wakatime/%s' % (ST_VERSION, __version__)
            cmd = [
                python,
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
                output, err = process.communicate(input=inp)
                output = u(output)
                retcode = process.poll()
                if (not retcode or retcode == 102) and not output:
                    self.sent()
                else:
                    update_status_bar('Error')
                if retcode:
                    log(DEBUG if retcode == 102 else ERROR, 'wakatime-core exited with status: {0}'.format(retcode))
                if output:
                    log(ERROR, u('wakatime-core output: {0}').format(output))
            except:
                log(ERROR, u(sys.exc_info()[1]))
                update_status_bar('Error')

        else:
            log(ERROR, 'Unable to find python binary.')
            update_status_bar('Error')

    def sent(self):
        update_status_bar('OK')


def download_python():
    thread = DownloadPython()
    thread.start()


class DownloadPython(threading.Thread):
    """Non-blocking thread for extracting embeddable Python on Windows machines.
    """

    def run(self):
        log(INFO, 'Downloading embeddable Python...')

        ver = '3.8.1'
        arch = 'amd64' if platform.architecture()[0] == '64bit' else 'win32'
        url = 'https://www.python.org/ftp/python/{ver}/python-{ver}-embed-{arch}.zip'.format(
            ver=ver,
            arch=arch,
        )

        if not os.path.exists(resources_folder()):
            os.makedirs(resources_folder())

        zip_file = os.path.join(resources_folder(), 'python.zip')
        try:
            urllib.urlretrieve(url, zip_file)
        except AttributeError:
            urllib.request.urlretrieve(url, zip_file)

        log(INFO, 'Extracting Python...')
        with contextlib.closing(ZipFile(zip_file)) as zf:
            path = os.path.join(resources_folder(), 'python')
            zf.extractall(path)

        try:
            os.remove(zip_file)
        except:
            pass

        log(INFO, 'Finished extracting Python.')


def plugin_loaded():
    global SETTINGS
    SETTINGS = sublime.load_settings(SETTINGS_FILE)

    log(INFO, 'Initializing WakaTime plugin v%s' % __version__)
    update_status_bar('Initializing...')

    if not python_binary():
        log(WARNING, 'Python binary not found.')
        if is_win:
            set_timeout(download_python, 0)
        else:
            sublime.error_message("Unable to find Python binary!\nWakaTime needs Python to work correctly.\n\nGo to https://www.python.org/downloads")
            return

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
