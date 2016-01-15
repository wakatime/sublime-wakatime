""" ==========================================================
File:        WakaTime.py
Description: Automatic time tracking for Sublime Text 2 and 3.
Maintainer:  WakaTime <support@wakatime.com>
License:     BSD, see LICENSE for more details.
Website:     https://wakatime.com/
==========================================================="""


__version__ = '6.0.4'


import sublime
import sublime_plugin

import os
import platform
import re
import sys
import time
import threading
import urllib
import webbrowser
from datetime import datetime
from zipfile import ZipFile
from subprocess import Popen, STDOUT, PIPE
try:
    import _winreg as winreg  # py2
except ImportError:
    try:
        import winreg  # py3
    except ImportError:
        winreg = None


is_py2 = (sys.version_info[0] == 2)
is_py3 = (sys.version_info[0] == 3)

if is_py2:
    def u(text):
        if text is None:
            return None
        try:
            text = str(text)
            return text.decode('utf-8')
        except:
            try:
                return text.decode(sys.getdefaultencoding())
            except:
                try:
                    return unicode(text)
                except:
                    return text

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
            return text

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
LOCK = threading.RLock()
PYTHON_LOCATION = None


# Log Levels
DEBUG = 'DEBUG'
INFO = 'INFO'
WARNING = 'WARNING'
ERROR = 'ERROR'


# add wakatime package to path
sys.path.insert(0, os.path.join(PLUGIN_DIR, 'packages'))
try:
    from wakatime.base import parseConfigFile
except ImportError:
    pass


def log(lvl, message, *args, **kwargs):
    try:
        if lvl == DEBUG and not SETTINGS.get('debug'):
            return
        msg = message
        if len(args) > 0:
            msg = message.format(*args)
        elif len(kwargs) > 0:
            msg = message.format(**kwargs)
        print('[WakaTime] [{lvl}] {msg}'.format(lvl=lvl, msg=msg))
    except RuntimeError:
        sublime.set_timeout(lambda: log(lvl, message, *args, **kwargs), 0)


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
            log(ERROR, 'Could not prompt for api key because no window found.')
    return False


def python_binary():
    if PYTHON_LOCATION is not None:
        return PYTHON_LOCATION

    # look for python in PATH and common install locations
    paths = [
        os.path.join(os.path.expanduser('~'), '.wakatime', 'python'),
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
        if SETTINGS.get('debug'):
            log(DEBUG, 'Could not read registry value "{reg}\\{key}".'.format(
                reg=reg,
                key=location,
            ))

    return val


def find_python_in_folder(folder, headless=True):
    pattern = re.compile(r'\d+\.\d+')

    path = 'python'
    if folder is not None:
        path = os.path.realpath(os.path.join(folder, 'python'))
    if headless:
        path = u(path) + u('w')
    log(DEBUG, u('Looking for Python at: {0}').format(path))
    try:
        process = Popen([path, '--version'], stdout=PIPE, stderr=STDOUT)
        output, err = process.communicate()
        output = u(output).strip()
        retcode = process.poll()
        log(DEBUG, u('Python Version Output: {0}').format(output))
        if not retcode and pattern.search(output):
            return path
    except:
        log(DEBUG, u('Python Version Output: {0}').format(u(sys.exc_info()[1])))

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
    """Non-blocking thread for sending heartbeats to api.
    """

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
            log(ERROR, 'missing api key.')
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
            log(DEBUG, ' '.join(obfuscate_apikey(cmd)))
            try:
                if not self.debug:
                    Popen(cmd)
                    self.sent()
                else:
                    process = Popen(cmd, stdout=PIPE, stderr=STDOUT)
                    output, err = process.communicate()
                    output = u(output)
                    retcode = process.poll()
                    if (not retcode or retcode == 102) and not output:
                        self.sent()
                    if retcode:
                        log(DEBUG if retcode == 102 else ERROR, 'wakatime-core exited with status: {0}'.format(retcode))
                    if output:
                        log(ERROR, u('wakatime-core output: {0}').format(output))
            except:
                log(ERROR, u(sys.exc_info()[1]))
        else:
            log(ERROR, 'Unable to find python binary.')

    def sent(self):
        sublime.set_timeout(self.set_status_bar, 0)
        sublime.set_timeout(self.set_last_heartbeat, 0)

    def set_status_bar(self):
        if SETTINGS.get('status_bar_message'):
            self.view.set_status('wakatime', datetime.now().strftime(SETTINGS.get('status_bar_message_fmt')))

    def set_last_heartbeat(self):
        global LAST_HEARTBEAT
        LAST_HEARTBEAT = {
            'file': self.target_file,
            'time': self.timestamp,
            'is_write': self.is_write,
        }


class DownloadPython(threading.Thread):
    """Non-blocking thread for extracting embeddable Python on Windows machines.
    """

    def run(self):
        log(INFO, 'Downloading embeddable Python...')

        ver = '3.5.0'
        arch = 'amd64' if platform.architecture()[0] == '64bit' else 'win32'
        url = 'https://www.python.org/ftp/python/{ver}/python-{ver}-embed-{arch}.zip'.format(
            ver=ver,
            arch=arch,
        )

        if not os.path.exists(os.path.join(os.path.expanduser('~'), '.wakatime')):
            os.makedirs(os.path.join(os.path.expanduser('~'), '.wakatime'))

        zip_file = os.path.join(os.path.expanduser('~'), '.wakatime', 'python.zip')
        try:
            urllib.urlretrieve(url, zip_file)
        except AttributeError:
            urllib.request.urlretrieve(url, zip_file)

        log(INFO, 'Extracting Python...')
        with ZipFile(zip_file) as zf:
            path = os.path.join(os.path.expanduser('~'), '.wakatime', 'python')
            zf.extractall(path)

        try:
            os.remove(zip_file)
        except:
            pass

        log(INFO, 'Finished extracting Python.')


def plugin_loaded():
    global SETTINGS
    log(INFO, 'Initializing WakaTime plugin v%s' % __version__)

    SETTINGS = sublime.load_settings(SETTINGS_FILE)

    if not python_binary():
        log(WARNING, 'Python binary not found.')
        if platform.system() == 'Windows':
            thread = DownloadPython()
            thread.start()
        else:
            sublime.error_message("Unable to find Python binary!\nWakaTime needs Python to work correctly.\n\nGo to https://www.python.org/downloads")
            return

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
