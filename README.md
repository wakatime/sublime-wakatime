sublime-wakatime
================

Metrics, insights, and time tracking automatically generated from your programming activity.


Installation
------------

1. Install [Package Control](https://packagecontrol.io/installation).

2. In Sublime, press `ctrl+shift+p`(Windows, Linux) or `cmd+shift+p`(OS X).

3. Type `install`, then press `enter` with `Package Control: Install Package` selected.

4. Type `wakatime`, then press `enter` with the `WakaTime` plugin selected.

5. Enter your [api key](https://wakatime.com/settings#apikey), then press `enter`.

6. Use Sublime and your coding activity will be displayed on your [WakaTime dashboard](https://wakatime.com).


Screen Shots
------------

![Project Overview](https://wakatime.com/static/img/ScreenShots/Screen-Shot-2016-03-21.png)


Unresponsive Plugin Warning
---------------------------

In Sublime Text 2, if you get a warning message:

    A plugin (WakaTime) may be making Sublime Text unresponsive by taking too long (0.017332s) in its on_modified callback.

To fix this, go to `Preferences → Settings - User` then add the following setting:

`"detect_slow_plugins": false`


Troubleshooting
---------------

First, turn on debug mode in your `WakaTime.sublime-settings` file.

![sublime user settings](https://wakatime.com/static/img/ScreenShots/sublime-wakatime-settings-menu.png?v=3)

Add the line: `"debug": true`

Then, open your Sublime Console with `View → Show Console` ( CTRL + \` ) to see the plugin executing the wakatime cli process when sending a heartbeat.
Also, tail your `$HOME/.wakatime.log` file to debug wakatime cli problems.

The [How to Debug Plugins][how to debug] guide shows how to check when coding activity was last received from your editor using the [User Agents API][user agents api].
For more general troubleshooting info, see the [wakatime-cli Troubleshooting Section][wakatime-cli-help].


[wakatime-cli-help]: https://github.com/wakatime/wakatime#troubleshooting
[how to debug]: https://wakatime.com/faq#debug-plugins
[user agents api]: https://wakatime.com/developers#user_agents
