"""Optional queue-position poller (HexChat + Linux only).

This is the ONLY part of interview-notify that SENDS to IRC. It does not open
its own connection: it drives your already-running HexChat client over its
D-Bus interface, so the message goes out on your real session (same nick, same
home connection). It periodically PMs a bot a command (by default `!position`)
on a randomized interval.

USE AT YOUR OWN RISK. Automated messages can look like botting. Private
trackers (RED among them) penalize automation and idling, so keep the interval
long, and don't enable this unless you accept that risk.

Requires system `python3-dbus` and a running HexChat. NOTE: a pipenv/virtualenv
is isolated from the system python3-dbus, so `import dbus` will fail inside one
even though the package is installed. Run this with your system python3, or make
the venv with --system-site-packages.
"""

import logging, threading, random, sys


def send_via_hexchat(target, command, context_channel=None, context_server=None):
  """PM `command` to `target` through the running HexChat client (one D-Bus call)."""
  import dbus  # lazy import: only needed when the poller is actually enabled
  bus = dbus.SessionBus()
  remote = bus.get_object('org.hexchat.service', '/org/hexchat/Remote')
  conn = dbus.Interface(remote, 'org.hexchat.connection')
  # Connect() takes (name, desc, version, ''), returns a per-client plugin path
  path = conn.Connect('interview-notify', 'queue position poller', '1.0', '')
  try:
    plugin = dbus.Interface(bus.get_object('org.hexchat.service', path), 'org.hexchat.plugin')
    if context_channel or context_server:
      ctx = plugin.FindContext(context_server or '', context_channel or '')
      if not int(ctx):
        raise RuntimeError('HexChat has no open context for server={!r} channel={!r} '
                           '- are you connected to it?'.format(context_server, context_channel))
      plugin.SetContext(ctx)
    plugin.Command('msg {} {}'.format(target, command))
  finally:
    conn.Disconnect()  # Disconnect lives on the connection interface, not the plugin


def _poll_loop(stop_event, target, command, interval_min, interval_max, context_channel, context_server):
  """Send `command` to `target` once immediately, then on a random interval until stopped."""
  while not stop_event.is_set():
    try:
      send_via_hexchat(target, command, context_channel, context_server)
      logging.info('position poller: sent "{}" to {}'.format(command, target))
    except Exception as e:
      logging.warning('position poller: send failed ({}: {})'.format(type(e).__name__, e))
    delay = random.uniform(interval_min, interval_max)
    logging.info('position poller: next "{}" to {} in {:.0f}s'.format(command, target, delay))
    if stop_event.wait(delay):  # interruptible sleep between sends
      break


def start(stop_event, target, command='!position', interval_min=1800, interval_max=3600,
          context_channel=None, context_server=None):
  """Start the poller in a background thread. Returns the thread, or None if unavailable.

  Only reached when the user explicitly passed --poll-position. On an
  unsupported setup (e.g. Windows, or no python3-dbus) we say exactly what is
  needed rather than failing silently or crashing. Users who do NOT request the
  feature never import this module, so they are unaffected.
  """
  try:
    import dbus
  except ImportError:
    logging.error('--poll-position needs the python3-dbus module, which this Python ({}) cannot '
                  'import. Install it from your distro (apt/dnf install python3-dbus, or pacman -S '
                  'python-dbus) - NOT pip. If it IS installed but you are in a pipenv/virtualenv, '
                  'the venv hides the system module: run with your system python3, or recreate the '
                  'venv with --system-site-packages. Continuing without the position poller.'.format(sys.executable))
    return None
  try:
    dbus.SessionBus()
  except Exception as e:
    logging.error('--poll-position needs a D-Bus session bus (Linux/HexChat only), which is '
                  'unavailable here ({}). Continuing without the position poller.'.format(e))
    return None
  thread = threading.Thread(
    target=_poll_loop,
    args=(stop_event, target, command, interval_min, interval_max, context_channel, context_server),
    daemon=True)
  thread.start()
  logging.info('position poller: enabled - "{}" to {} every {:.0f}-{:.0f} min (jittered)'.format(
    command, target, interval_min / 60, interval_max / 60))
  return thread
