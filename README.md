sublime-wakatime
================

Metrics, insights, and time tracking automatically generated from your programming activity.


Installation
------------

1. Install [Package Control](https://packagecontrol.io/installation).

2. Using [Package Control](https://packagecontrol.io/docs/usage):

  a) Inside Sublime, press `ctrl+shift+p`(Windows, Linux) or `cmd+shift+p`(OS X).

  b) Type `install`, then press `enter` with `Package Control: Install Package` selected.

  c) Type `wakatime`, then press `enter` with the `WakaTime` plugin selected.

3. Enter your [api key](https://wakatime.com/settings#apikey), then press `enter`.

4. Use Sublime and your time will be tracked for you automatically.

5. Visit https://wakatime.com/dashboard to see your logged time.


Screen Shots
------------

![Project Overview](https://wakatime.com/static/img/ScreenShots/Screen-Shot-2016-03-21.png)


Unresponsive Plugin Warning
---------------------------

In Sublime Text 2, if you get a warning message:

    A plugin (WakaTime) may be making Sublime Text unresponsive by taking too long (0.017332s) in its on_modified callback.

To fix this, go to `Preferences > Settings - User` then add the following setting:

`"detect_slow_plugins": false`


Troubleshooting
---------------

First, turn on debug mode in your `WakaTime.sublime-settings` file.

![sublime user settings](https://wakatime.com/static/img/ScreenShots/sublime-wakatime-settings-menu.png?v=3)

Add the line: `"debug": true`

Then, open your Sublime Console with `View -> Show Console` to see the plugin executing the wakatime cli process when sending a heartbeat. Also, tail your `$HOME/.wakatime.log` file to debug wakatime cli problems.

For more general troubleshooting information, see [wakatime/wakatime#troubleshooting](https://github.com/wakatime/wakatime#troubleshooting).
