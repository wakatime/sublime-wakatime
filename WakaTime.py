""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""


__version__ = '8.0.6'


import sublime
import sublime_plugin

import contextlib
import json
import os
import platform
import re
import sys
import time
import threading
import traceback
import urllib
import webbrowser
from datetime import datetime
from subprocess import Popen, STDOUT, PIPE
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
PYTHON_LOCATION = None
HEARTBEATS = queue.Queue()


# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


# add wakatime package to path
sys.path.insert(0, os.path.join(PLUGIN_DIR, 'packages'))
try:
    from wakatime.main import parseConfigFile
except ImportError:
    pass


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
    if platform.system() == 'Windows':
        return os.path.join(os.getenv('APPDATA'), 'WakaTime')
    else:
        return os.path.join(os.path.expanduser('~'), '.wakatime')


def update_status_bar(status):
    """Updates the status bar."""

    try:
        if SETTINGS.get('status_bar_message'):
            msg = datetime.now().strftime(SETTINGS.get('status_bar_message_fmt'))
            if '{status}' in msg:
                msg = msg.format(status=status)

            active_window = sublime.active_window()
            if active_window:
                for view in active_window.views():
                    view.set_status('wakatime', msg)
    except RuntimeError:
        set_timeout(lambda: update_status_bar(status), 0)


def prompt_api_key():
    global SETTINGS

    if SETTINGS.get('api_key'):
        return True

    default_key = ''
    try:
        configs = parseConfigFile()
        if configs is not None:
            if configs.has_option('settings', 'api_key'):
                default_key = configs.get('settings', 'api_key')
    except:
        pass

    window = sublime.active_window()
    if window:
        def got_key(text):
            if text:
                SETTINGS.set('api_key', str(text))
                sublime.save_settings(SETTINGS_FILE)
        window.show_input_panel('[WakaTime] Enter your wakatime.com api key:', default_key, got_key, None, None)
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
    if platform.system() != 'Windows' or winreg is None:
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


def find_python_in_folder(folder, headless=True):
    pattern = re.compile(r'\d+\.\d+')

    path = 'python'
    if folder is not None:
        path = os.path.realpath(os.path.join(folder, 'python'))
    if headless:
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

    if headless:
        path = find_python_in_folder(folder, headless=False)
        if path is not None:
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
    seconds = 4
    set_timeout(process_queue, seconds)


def process_queue():
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
        self.api_key = SETTINGS.get('api_key', '')
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
                extra_heartbeats = [self.build_heartbeat(**x) for x in self.extra_heartbeats]
                extra_heartbeats = json.dumps(extra_heartbeats)
            else:
                extra_heartbeats = None
                stdin = None

            log(DEBUG, ' '.join(obfuscate_apikey(cmd)))
            try:
                process = Popen(cmd, stdin=stdin, stdout=PIPE, stderr=STDOUT)
                inp = None
                if self.has_extra_heartbeats:
                    inp = "{0}\n".format(extra_heartbeats)
                    inp = inp.encode('utf-8')
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

        ver = '3.5.2'
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
    update_status_bar('Initializing')

    if not python_binary():
        log(WARNING, 'Python binary not found.')
        if platform.system() == 'Windows':
            set_timeout(download_python, 0)
        else:
            sublime.error_message("Unable to find Python binary!\nWakaTime needs Python to work correctly.\n\nGo to https://www.python.org/downloads")
            return

    after_loaded()


def after_loaded():
    if not prompt_api_key():
        set_timeout(after_loaded, 0.5)


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
