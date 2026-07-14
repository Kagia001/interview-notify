# interview-notify
Push notifications from IRC for your private tracker interviews

Heads up: the original project sends anonymous telemetry via ntfy. Specifically, your nick hashed, mode (red/orp), and version. I have not removed this, since the data collected is very minimal and your IP cannot be saved, but I think this should be disclosed. If you wish to disable this, you may comment out lines 156-158 in interview_notify.py.

<img src="https://i.imgur.com/ZLFyxgY.png">

## features

this script parses log files from your irc client and attempts to be client-agnostic.

it sends push notifications when:
- interviews are happening (toggle with `--no-notify-others`)
- YOUR interview is happening! (detected from the queue announcement, the voice grant, or a moderator's manual "say/type my name" invite)
- someone mentions you
- your queue position reaches a threshold (default #10, see `--position-alert`)
- you lose your spot in the queue due to a netsplit
- you get kicked

it watches every recently-active log file in `--log-dir`, not just the newest, so an interview and its separate announcement channel are both seen.

there is also an optional queue-position poller and a companion report tool — see below.

## installing

- install python3. i suggest homebrew, winget, or just use the installer: https://www.python.org/downloads/
  - _this script might require python3.11_
- install the `requests` module with `pip3 install requests` (or use `pipenv install` to automatically install dependencies)
- clone this repo
  - `git clone https://github.com/ftc2/interview-notify.git`
- `python3 interview_notify.py`

**The optional `--poll-position` feature needs Linux, a running HexChat, and the system `python3-dbus` module.** Install it from your distro, NOT pip (pip's `dbus-python` compiles against system libraries and usually fails):
- Debian/Ubuntu: `apt install python3-dbus`
- Fedora: `dnf install python3-dbus`
- Arch: `pacman -S python-dbus`

**Gotcha:** this repo ships a `Pipfile`, so if you `pipenv install` you end up in a virtualenv that is isolated from the system `python3-dbus` — the poller then fails with a "cannot import dbus" error *even though the package is installed*. Fix: run interview-notify with your **system** `python3` (which also needs `requests`: `apt install python3-requests`), or recreate the venv with `--system-site-packages`. Everything except the poller works fine inside the venv; the poller is off by default.

## using

pretty self explanatory if you read the help:

```
./interview_notify.py -h

usage: interview_notify.py [-h] --topic TOPIC [--server SERVER] --log-dir PATH --nick NICK [--notify-others | --no-notify-others] [--position-alert N] [--poll-position] [--poll-interval MIN,MAX]
                           [--check-bot-nicks | --no-check-bot-nicks] [--bot-nicks NICKS] [--mode {red,ops}] [-v] [--version]

IRC Interview Notifier v1.3.0
https://github.com/ftc2/interview-notify

options:
  -h, --help            show this help message and exit
  --topic TOPIC         ntfy topic name to POST notifications to
  --server SERVER       ntfy server to POST notifications to – default: https://ntfy.sh/
  --log-dir PATH        path to IRC logs (continuously checks for recently-active files to parse)
  --nick NICK           your IRC nick
  --notify-others, --no-notify-others
                        notify when someone else is called to interview – default: enabled
  --position-alert N    notify the first time your queue position reaches N or below; 0 to disable – default: 10
  --poll-position       periodically PM !position to the bot via a running HexChat client (Linux/HexChat only, uses your existing connection) – default: disabled
  --poll-interval MIN,MAX
                        random minutes between !position sends – default: 30,60
  --check-bot-nicks, --no-check-bot-nicks
                        attempt to parse bot's nick. disable if your log files are not like '<nick> message' – default: enabled
  --bot-nicks NICKS     comma-separated list of bot nicks to watch – default: Gatekeeper
  --mode {red,ops}      interview mode (affects triggers) – default: red
  -v                    verbose (invoke multiple times for more verbosity)
  --version             show program's version number and exit

Sends a push notification with https://ntfy.sh/ when it's your turn to interview.
They have a web client and mobile clients. You can have multiple clients subscribed to this.
Wherever you want notifications: open the client, 'Subscribe to topic', pick a unique topic
  name for this script, and use that everywhere.
On mobile, I suggest enabling the 'Instant delivery' feature as well as 'Keep alerting for
  highest priority'. These will enable fastest and most reliable delivery of the
  notification, and your phone will continuously alarm when your interview is ready.
```

## queue position

`--position-alert N` (default 10) notifies you the first time the bot reports your position at #N or below. It reads the bot's `You are in position N of M` replies out of your logs, so it works whether you check `!position` by hand or use the poller below. It re-arms if your position climbs back above the threshold (e.g. after a netsplit reset). Set `--position-alert 0` to turn it off.

`--poll-position` (off by default) keeps that position fresh automatically by PMing `!position` to the bot every `--poll-interval MIN,MAX` minutes (default 30–60, randomized). **It does not open its own IRC connection** — it drives your already-running HexChat client over its D-Bus interface, so the message goes out on your real session (same nick, same home connection). This is HexChat + Linux only and needs `python3-dbus`; if it can't run it says so and the notifier keeps working. It is the only part of the project that sends to IRC, so use a sensible (long) interval.

## interview report

`interview_report.py` is a separate, read-only tool that scans the same logs and prints a table of when interviews were called and how they ended (pass / fail / missed), by pairing each `Currently interviewing:` announcement with the bot's later verdict kick:

```
./interview_report.py --log-dir /path/to/logs --nick your_nick
```

Add `--positions` to also print your queue position over time.

## testing/troubleshooting

first, use `-v` and make sure you can see new messages from IRC showing up:

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick -v`

### testing notifications

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick --bot-nicks Gatekeeper,your_nick -v`

then type `Currently interviewing: your_nick` in IRC.

if it doesn't work, maybe you have a wonky log file format. try with `--no-check-bot-nicks`:

`interview_notify.py --topic your_topic --log-dir /path/to/logs --nick your_nick --no-check-bot-nicks -v`
