# What is this?
Quick and dirty Python 2.7 script to save all private messages from a Discord user account to local files. It saves the last point where messages were downloaded to allow repeat runs without hitting the Discord API unnecessarily.

# How do I get my Discord user token?
I'm not sure if there's a cleaner way to do this, the API documentation doesn't mention anything about it if so. Log into the Discord client, press control+shift+I to get into the Chrome developer tools, and type "localStorage.token" into the console. Paste the value (without quotes) into the appropriate area at the top of this script as shown. The script supports pulling multiple users if desired.

# Installation

This is not tested on any platform besides Linux, but I don't see any reason it shouldn't work on Windows.

Download the script and install the following libraries with pip:

pip install requests python-dateutil unidecode
