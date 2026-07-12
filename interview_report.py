#!/usr/bin/env python3
"""Scan IRC logs and print when interviews were called and how they ended.

Read-only. Pairs each "Currently interviewing: <nick>" announcement with the
Gatekeeper kick that later delivers the verdict (pass / fail / missed).
"""

import argparse, re, sys
from pathlib import Path
from datetime import datetime, timedelta

# a verdict must land within this long after the call to count as its result
MATCH_WINDOW = timedelta(hours=6)
# the same outcome can be logged in more than one channel; collapse near-duplicates
DEDUP_WINDOW = timedelta(minutes=5)

TS = re.compile(r'^(\w{3} \d{2} \d{2}:\d{2}:\d{2}) ')
YEAR = re.compile(r'BEGIN LOGGING AT .* (\d{4})')
CALL = re.compile(r'Currently interviewing: (\S+) ::: (#\S+) ::: (\d+) remaining')
KICK = re.compile(r'Gatekeeper has kicked (\S+) from #\S+ \((.*)\)')
SELF_KICK = re.compile(r'You have been kicked from #\S+ by Gatekeeper \((.*)\)')
POSITION = re.compile(r'You are in position (\d+) of (\d+)')

def verdict(reason):
  """Map a kick reason to an interview outcome, or None if it isn't one."""
  if reason.startswith('Congratulations') or 'Welcome to' in reason:
    return 'PASS'
  if 'not passed the interview' in reason:
    return 'FAIL'
  if 'missed your interview' in reason:
    return 'MISSED'
  return None

def parse_logs(paths, nick):
  calls, results = [], []
  for path in paths:
    year = datetime.now().year
    with open(path, encoding='utf-8', errors='replace') as f:
      for line in f:
        y = YEAR.search(line)
        if y:
          year = int(y.group(1))
          continue
        m = TS.match(line)
        if not m:
          continue
        try:
          when = datetime.strptime('{} {}'.format(year, m.group(1)), '%Y %b %d %H:%M:%S')
        except ValueError:
          continue
        c = CALL.search(line)
        if c:
          calls.append({'when': when, 'nick': c.group(1), 'room': c.group(2), 'queue': c.group(3)})
          continue
        k = KICK.search(line)
        if k and verdict(k.group(2)):
          results.append({'when': when, 'nick': k.group(1), 'outcome': verdict(k.group(2))})
          continue
        s = nick and SELF_KICK.search(line)
        if s and verdict(s.group(1)):
          results.append({'when': when, 'nick': nick, 'outcome': verdict(s.group(1))})
  calls.sort(key=lambda r: r['when'])
  results.sort(key=lambda r: r['when'])
  deduped = []
  for r in results:
    if any(d['nick'] == r['nick'] and d['outcome'] == r['outcome']
           and abs((d['when'] - r['when']).total_seconds()) <= DEDUP_WINDOW.total_seconds()
           for d in deduped):
      continue
    deduped.append(r)
  return calls, deduped

def match(calls, results):
  used = set()
  for call in calls:
    call['result'] = None
    for i, r in enumerate(results):
      if i in used or r['nick'] != call['nick']:
        continue
      if call['when'] <= r['when'] <= call['when'] + MATCH_WINDOW:
        used.add(i)
        call['result'] = r
        break
  orphans = [r for i, r in enumerate(results) if i not in used]
  return orphans

def parse_positions(paths):
  """Extract every "You are in position N of M" observation, in time order."""
  obs = []
  for path in paths:
    year = datetime.now().year
    with open(path, encoding='utf-8', errors='replace') as f:
      for line in f:
        y = YEAR.search(line)
        if y:
          year = int(y.group(1))
          continue
        m = TS.match(line)
        p = m and POSITION.search(line)
        if not p:
          continue
        try:
          when = datetime.strptime('{} {}'.format(year, m.group(1)), '%Y %b %d %H:%M:%S')
        except ValueError:
          continue
        obs.append({'when': when, 'pos': int(p.group(1)), 'total': int(p.group(2))})
  obs.sort(key=lambda o: o['when'])
  return obs

def print_positions(obs):
  print('\nPOSITION OVER TIME (your queue position; unchanged observations collapsed)')
  print('{:<17} {:>5} {:>6} {:>7}'.format('WHEN', 'POS', 'OF', 'CHANGE'))
  print('-' * 40)
  prev = None
  for o in obs:
    if o['pos'] == prev:
      continue
    change = '' if prev is None else '{:+d}'.format(o['pos'] - prev)
    print('{:<17} {:>5} {:>6} {:>7}'.format(o['when'].strftime('%b %d %H:%M'), o['pos'], o['total'], change))
    prev = o['pos']
  print('-' * 40)
  if obs:
    best = min(obs, key=lambda o: o['pos'])
    print('{} observations | best: #{} on {}'.format(len(obs), best['pos'], best['when'].strftime('%b %d %H:%M')))

def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument('--log-dir', required=True, type=Path, help='directory of IRC log files')
  ap.add_argument('--nick', help='your nick, to also attribute your own "You have been kicked" results')
  ap.add_argument('--positions', action='store_true', help='also print your queue position over time')
  args = ap.parse_args()
  if not args.log_dir.is_dir():
    sys.exit('log-dir is not a directory')

  paths = sorted(p for p in args.log_dir.iterdir() if p.is_file() and p.suffix == '.log')
  calls, results = parse_logs(paths, args.nick)
  orphans = match(calls, results)

  print('{:<17} {:<20} {:<18} {:>5}  {:<8} {:<17} {:>7}'.format(
    'CALLED', 'INTERVIEWEE', 'ROOM', 'QUEUE', 'RESULT', 'RESULT AT', 'ELAPSED'))
  print('-' * 96)
  tally = {}
  for c in calls:
    r = c['result']
    if r:
      elapsed = r['when'] - c['when']
      mins = int(elapsed.total_seconds() // 60)
      res, at, el = r['outcome'], r['when'].strftime('%b %d %H:%M'), '{}h{:02d}m'.format(mins // 60, mins % 60)
    else:
      res, at, el = '—', '(no result in log)', ''
    tally[res] = tally.get(res, 0) + 1
    print('{:<17} {:<20} {:<18} {:>5}  {:<8} {:<17} {:>7}'.format(
      c['when'].strftime('%b %d %H:%M'), c['nick'], c['room'], c['queue'], res, at, el))

  print('-' * 96)
  print('{} interviews called | '.format(len(calls))
        + ' '.join('{}: {}'.format(k, v) for k, v in sorted(tally.items())))
  if orphans:
    print('\nResults with no matching call in the logs (interview began before the log window):')
    for r in orphans:
      print('  {}  {:<20} {}'.format(r['when'].strftime('%b %d %H:%M'), r['nick'], r['outcome']))

  if args.positions:
    print_positions(parse_positions(paths))

if __name__ == '__main__':
  main()
