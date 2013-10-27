
History
-------


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

