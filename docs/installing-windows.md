## Installing on Windows

We recommend that use you use a *unix system to run CloudBot in production, or Vagrant when developing CloudBot. However, it is possible to install natively on Windows.

First, make sure you have python3.4 installed. It can be downloaded at [python.org](https://www.python.org/downloads/release/python-341/).

Next, you need to install `pip`.

You can usually install `pip` via the following python command in cmd:
```
python3.4 -m ensurepip
```

If that doesn't work, follow [this guide](http://simpledeveloper.com/how-to-install-easy_install/) and then run `easy_install pip` in cmd.

### Download

Download CloudBotRefresh from [https://github.com/CloudBotIRC/CloudBot/zipball/python3.4.zip](https://github.com/CloudBotIRC/CloudBotRefresh/archive/python3.4.zip).

Unzip the resulting file, and continue to read this document.

### Install

Before you can run the bot, you need to install a few Python dependencies. All of CloudBotRefresh's dependencies are stored in the `requirements.txt` file.`

These can be installed with `pip` (The Python package manager) by running the following command in the bot directory:

    pip install -r requirements.txt

Note for **Windows** users: Windows compatibility some modules is **broken** (such as ping), but we do intend to add it, eventually.
