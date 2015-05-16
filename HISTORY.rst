
History
-------


4.0.6 (2015-05-16)
++++++++++++++++++

- fix bug with auto detecting project name
- upgrade wakatime cli to v4.0.13


4.0.5 (2015-05-15)
++++++++++++++++++

- correctly display caller and lineno in log file when debug is true
- project passed with --project argument will always be used
- new --alternate-project argument
- upgrade wakatime cli to v4.0.12


4.0.4 (2015-05-12)
++++++++++++++++++

- reuse SSL connection over multiple processes for improved performance
- upgrade wakatime cli to v4.0.11


4.0.3 (2015-05-06)
++++++++++++++++++

- send cursorpos to wakatime cli
- upgrade wakatime cli to v4.0.10


4.0.2 (2015-05-06)
++++++++++++++++++

- only send heartbeats for the currently active buffer


4.0.1 (2015-05-06)
++++++++++++++++++

- ignore git temporary files
- don't send two write heartbeats within 2 seconds of eachother


4.0.0 (2015-04-12)
++++++++++++++++++

- listen for selection modified instead of buffer activated for better performance


3.0.19 (2015-04-07)
+++++++++++++++++++

- fix bug in project detection when folder not found


3.0.18 (2015-04-04)
+++++++++++++++++++

- upgrade wakatime cli to v4.0.8
- added api_url config option to .wakatime.cfg file


3.0.17 (2015-04-02)
+++++++++++++++++++

- use open folder as current project when not using revision control


3.0.16 (2015-04-02)
+++++++++++++++++++

- copy list when obfuscating api key so original command is not modified


3.0.15 (2015-04-01)
+++++++++++++++++++

- obfuscate api key when logging to Sublime Text Console in debug mode


3.0.14 (2015-03-31)
+++++++++++++++++++

- always use external python binary because ST builtin python does not support checking SSL certs
- upgrade wakatime cli to v4.0.6


3.0.13 (2015-03-23)
+++++++++++++++++++

- correctly check for SSL support in ST built-in python
- fix status bar message


3.0.12 (2015-03-23)
+++++++++++++++++++

- always use unicode function from compat module when encoding log messages


3.0.11 (2015-03-23)
+++++++++++++++++++

- upgrade simplejson package to v3.6.5


3.0.10 (2015-03-22)
+++++++++++++++++++

- ability to disable status bar message from WakaTime.sublime-settings file


3.0.9 (2015-03-20)
++++++++++++++++++

- status bar message showing when WakaTime plugin is enabled
- moved some logic into thread to help prevent slow plugin warning message


3.0.8 (2015-03-09)
++++++++++++++++++

- upgrade wakatime cli to v4.0.4
- use requests library instead of urllib2, so api SSL cert is verified
- new --notfile argument to support logging time without a real file
- new --proxy argument for https proxy support
- new options for excluding and including directories


3.0.7 (2015-02-05)
++++++++++++++++++

- handle errors encountered when looking for .sublime-project file


3.0.6 (2015-01-13)
++++++++++++++++++

- upgrade external wakatime package to v3.0.5
- ignore errors from malformed markup (too many closing tags)


3.0.5 (2015-01-06)
++++++++++++++++++

- upgrade external wakatime package to v3.0.4
- remove unused dependency, which is missing in some python environments


3.0.4 (2014-12-26)
++++++++++++++++++

- fix bug causing plugin to not work in Sublime Text 2


3.0.3 (2014-12-25)
++++++++++++++++++

- upgrade external wakatime package to v3.0.3
- detect JavaScript frameworks from script tags in Html template files


3.0.2 (2014-12-25)
++++++++++++++++++

- upgrade external wakatime package to v3.0.2
- detect frameworks from JavaScript and JSON files


3.0.1 (2014-12-23)
++++++++++++++++++

- parse use namespaces from php files


3.0.0 (2014-12-23)
++++++++++++++++++

- upgrade external wakatime package to v3.0.1
- detect libraries and frameworks for C++, Java, .NET, PHP, and Python files


2.0.21 (2014-12-22)
++++++++++++++++++

- upgrade external wakatime package to v2.1.11
- fix bug in offline logging when no response from api


2.0.20 (2014-12-05)
++++++++++++++++++

- upgrade external wakatime package to v2.1.9
- fix bug preventing offline heartbeats from being purged after uploaded


2.0.19 (2014-12-04)
++++++++++++++++++

- upgrade external wakatime package to v2.1.8
- fix UnicodeDecodeError when building user agent string
- handle case where response is None


2.0.18 (2014-11-30)
++++++++++++++++++

- upgrade external wakatime package to v2.1.7
- upgrade pygments to v2.0.1
- always log an error when api key is incorrect


2.0.17 (2014-11-18)
++++++++++++++++++

- upgrade external wakatime package to v2.1.6
- fix list index error when detecting subversion project


2.0.16 (2014-11-12)
++++++++++++++++++

- upgrade external wakatime package to v2.1.4
- when Python was not compiled with https support, log an error to the log file


2.0.15 (2014-11-10)
++++++++++++++++++

- upgrade external wakatime package to v2.1.3
- correctly detect branch for subversion projects


2.0.14 (2014-10-14)
++++++++++++++++++

- popup error message if Python binary not found


2.0.13 (2014-10-07)
++++++++++++++++++

- upgrade external wakatime package to v2.1.2
- still log heartbeat when something goes wrong while reading num lines in file


2.0.12 (2014-09-30)
++++++++++++++++++

- upgrade external wakatime package to v2.1.1
- fix bug where binary file opened as utf-8


2.0.11 (2014-09-30)
++++++++++++++++++

- upgrade external wakatime package to v2.1.0
- python3 compatibility changes


2.0.10 (2014-08-29)
++++++++++++++++++

- upgrade external wakatime package to v2.0.8
- supress output from svn command


2.0.9 (2014-08-27)
++++++++++++++++++

- upgrade external wakatime package to v2.0.7
- fix support for subversion projects on Mac OS X


2.0.8 (2014-08-07)
++++++++++++++++++

- upgrade external wakatime package to v2.0.6
- fix unicode bug by encoding json POST data


2.0.7 (2014-07-25)
++++++++++++++++++

- upgrade external wakatime package to v2.0.5
- option in .wakatime.cfg to obfuscate file names


2.0.6 (2014-07-25)
++++++++++++++++++

- upgrade external wakatime package to v2.0.4
- use unique logger namespace to prevent collisions in shared plugin environments


2.0.5 (2014-06-18)
++++++++++++++++++

- upgrade external wakatime package to v2.0.3
- use project name from sublime-project file when no revision control project found


2.0.4 (2014-06-09)
++++++++++++++++++

- upgrade external wakatime package to v2.0.2
- disable offline logging when Python not compiled with sqlite3 module


2.0.3 (2014-05-26)
++++++++++++++++++

- upgrade external wakatime package to v2.0.1
- fix bug in queue preventing completed tasks from being purged


2.0.2 (2014-05-26)
++++++++++++++++++

- disable syncing offline time until bug fixed


2.0.1 (2014-05-25)
++++++++++++++++++

- upgrade external wakatime package to v2.0.0
- offline time logging using sqlite3 to queue editor events


1.6.5 (2014-03-05)
++++++++++++++++++

- upgrade external wakatime package to v1.0.1
- use new domain wakatime.com


1.6.4 (2014-02-05)
++++++++++++++++++

- upgrade external wakatime package to v1.0.0
- support for mercurial revision control


1.6.3 (2014-01-15)
++++++++++++++++++

- upgrade common wakatime package to v0.5.3


1.6.2 (2014-01-14)
++++++++++++++++++

- upgrade common wakatime package to v0.5.2


1.6.1 (2013-12-13)
++++++++++++++++++

- upgrade common wakatime package to v0.5.1
- second line in .wakatime-project now sets branch name


1.6.0 (2013-12-13)
++++++++++++++++++

- upgrade common wakatime package to v0.5.0


1.5.2 (2013-12-03)
++++++++++++++++++

- use non-localized datetime in log


1.5.1 (2013-12-02)
++++++++++++++++++

- decode file names with filesystem encoding, then encode as utf-8 for logging


1.5.0 (2013-11-28)
++++++++++++++++++

- increase "ping" frequency from every 5 minutes to every 2 minutes
- prevent sending multiple api requests when saving the same file


1.4.12 (2013-11-21)
+++++++++++++++++++

- handle UnicodeDecodeError exceptions when json encoding log messages


1.4.11 (2013-11-13)
+++++++++++++++++++

- placing .wakatime-project file in a folder will read the project's name from that file


1.4.10 (2013-10-31)
++++++++++++++++++

- recognize jinja2 file extensions as HTML


1.4.9 (2013-10-28)
++++++++++++++++++

- handle case where ignore patterns not defined


1.4.8 (2013-10-27)
++++++++++++++++++

- new setting to ignore files that match a regular expression pattern


1.4.7 (2013-10-26)
++++++++++++++++++

- simplify some language lexer names into more common versions


1.4.6 (2013-10-25)
++++++++++++++++++

- force some file extensions to be recognized as certain language


1.4.5 (2013-10-14)
++++++++++++++++++

- remove support for subversion projects on Windows to prevent cmd window popups
- ignore all errors from pygments library


1.4.4 (2013-10-13)
++++++++++++++++++

- read git branch from .git/HEAD without running command line git client


1.4.3 (2013-09-30)
++++++++++++++++++

- send olson timezone string to api for displaying logged time in user's zone


1.4.2 (2013-09-30)
++++++++++++++++++

- print error code in Sublime's console if api request fails


1.4.1 (2013-09-30)
++++++++++++++++++

- fix SSL support problem for Linux users


1.4.0 (2013-09-22)
++++++++++++++++++

- log source code language type of files
- log total number of lines in files
- better python3 support


1.3.7 (2013-09-07)
++++++++++++++++++

- fix relative import bug


1.3.6 (2013-09-06)
++++++++++++++++++

- switch back to urllib2 instead of requests library in wakatime package


1.3.5 (2013-09-05)
++++++++++++++++++

- send Sublime version with api requests for easier debugging


1.3.4 (2013-09-04)
++++++++++++++++++

- upgraded wakatime package


1.3.3 (2013-09-04)
++++++++++++++++++

- using requests package in wakatime package


1.3.2 (2013-08-25)
++++++++++++++++++

- fix bug causing wrong file name detected
- misc bug fixes


1.3.0 (2013-08-15)
++++++++++++++++++

- detect git branches


1.2.0 (2013-08-12)
++++++++++++++++++

- run wakatime package in new process when no SSL support in Sublime


1.1.0 (2013-08-12)
++++++++++++++++++

- run wakatime package in main Sublime process


1.0.1 (2013-08-09)
++++++++++++++++++

- no longer beta for Package Control versioning requirement


0.4.2 (2013-08-08)
++++++++++++++++++

- remove away prompt popup


0.4.0 (2013-08-08)
++++++++++++++++++

- run wakatime package in background


0.3.3 (2013-08-06)
++++++++++++++++++

- support installing via Sublime Package Control


0.3.2 (2013-08-06)
++++++++++++++++++

- fixes for user sublime-settings file


0.3.1 (2013-08-04)
++++++++++++++++++

- renamed plugin folder


0.3.0 (2013-08-04)
++++++++++++++++++

- use WakaTime.sublime-settings file for configuration settings


0.2.10 (2013-07-29)
+++++++++++++++++++

- Python3 support
- better Windows support by detecting pythonw.exe location


0.2.9 (2013-07-22)
++++++++++++++++++

- upgraded wakatime package
- bug fix when detecting git repos


0.2.8 (2013-07-21)
++++++++++++++++++

- Windows bug fixes


0.2.7 (2013-07-20)
++++++++++++++++++

- prevent cmd window opening in background (Windows users only)


0.2.6 (2013-07-17)
++++++++++++++++++

- log errors from wakatime package to ~/.wakatime.log


0.2.5 (2013-07-17)
++++++++++++++++++

- distinguish between write events and normal events
- prompt user for api key if one does not already exist
- rename ~/.wakatime to ~/.wakatime.conf
- set away prompt to 5 minutes
- fix bug in custom logger


0.2.1 (2013-07-07)
++++++++++++++++++

- Birth

