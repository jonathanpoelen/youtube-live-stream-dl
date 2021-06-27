#!/usr/bin/env python3
from urllib.request import (urlopen, URLError)
from time import sleep
from threading import Thread
import argparse
import os
import subprocess
import sys
import re


def openfifo(filename):
  try:
    os.mkfifo(filename)
  except:
    os.remove(filename)
    os.mkfifo(filename)

  return open(filename, 'wb')

class PartDownloader():
  def __init__(self, filename_prefix:str, istart:int, istop:int):
    self.filename_prefix = filename_prefix
    self.istart = istart
    self.istop = istop

  def start(self, video_url, audio_url) -> tuple[str, str]:
    video_filename = self.filename_prefix + '.pipe.mp4'
    audio_filename = self.filename_prefix + '.pipe.m4a'

    self.video_thread = Thread(target=self._part_downloader,
                               args=(video_url, video_filename, 'video'))
    self.video_thread.start()

    self.audio_thread = Thread(target=self._part_downloader,
                               args=(audio_url, audio_filename, 'audio'))
    self.audio_thread.start()

    return (video_filename, audio_filename)

  def join(self) -> None:
    self.audio_thread.join()
    self.video_thread.join()

  def _part_downloader(self, url, filename, media):
    file = openfifo(filename)

    success = True
    i = self.istart

    while i < self.istop:
      try:
        with urlopen(f'{url}{i}') as f:
          file.write(f.read())
      except URLError as e:
        # file that may not exist yet, try again
        if not success:
          break
        success = False
        sleep(7)
        continue

      success = True
      i += 1
      print(f"Downloaded {media} part {i}")

# @[+-]HH:MM:SS or @[+-]HHhMMmSS
re_time = re.compile(r'^(@?[+-]?)(?:(?:(?:(\d+):)?(\d+):)?(\d+)|(?:(\d+)h)?(?:(\d+)m)?(\d*))$')

def _gtoint(m, i):
  n = m.group(i) or m.group(i+3)
  return int(n) if n else 0

def parse_time(s):
  if s == '@':
    return ('@', 0)

  m = re_time.match(s)
  try:
    hours = _gtoint(m, 2)
    minutes = _gtoint(m, 3)
    seconds = _gtoint(m, 4)
    sym = m.group(1)
    return ('' if sym == '@' else sym, hours * 3600 + minutes * 60 + seconds)
  except Exception as e:
    raise ValueError()

seconds_in_part = 5

re_pos = re.compile(r'^([+-])?(\d+)$')
def parse_pos(s):
  m = re_pos.match(s)
  return (m.group(1), int(m.group(2)) * seconds_in_part)


parser = argparse.ArgumentParser(
  formatter_class=argparse.RawDescriptionHelpFormatter,
  description='Youtube live stream downloader (https://github.com/jonathanpoelen/youtube-live-stream-dl).\nDownload parts from the Youtube Video that is live streamed, from start of the stream till the end.',
  epilog='''Time format: [@][+-][[HH:]MM:]SS or [@][+-][HHh][MMm][SS]
  HH expresses the number of hours, MM the number of minutes and, SS the number of seconds.

  NPart format: [@][+-]N
  N expresses the number of parts (sq parameter of url).

  @ refer to sq parameter in url and +/- is relative to -s/-S for -e/-E and vice versa.
  The sq parameter is automatically used when -s/-S and -e/-E are relative.

  # the whole stream
  youtube-live-stream-dl url1 url2

  # the first hour
  youtube-live-stream-dl -e 1h url1 url2

  # from the first hour to the end
  youtube-live-stream-dl -s 1h url1 url2

  # from sq to the end
  youtube-live-stream-dl -s @ ...&sq=720 url2

  # from 30m to sq (1h)
  youtube-live-stream-dl -s=-30m ...&sq=720 url2

  # from sq (1h) to 3h
  youtube-live-stream-dl -e +2h ...&sq=720 url2

  # start = sq (1h) + 30m
  # stop = start + 2h
  youtube-live-stream-dl -s=-30m -e +2h ...&sq=720 url2

  # stop = sq (1h) + 2h
  # start = stop - 30m
  youtube-live-stream-dl -s=-30m -e @+2h ...&sq=720 url2

  # start = sq (1h) - 30m
  # stop = sq (1h) + 2h
  youtube-live-stream-dl -s @-30m -e @+2h ...&sq=720 url2
  ''')
parser.add_argument('-s', '--start', metavar='TIME', type=parse_time, default=None)
parser.add_argument('-e', '--stop', metavar='TIME', type=parse_time, default=None)
parser.add_argument('-S', '--start-part', metavar='NPART', type=parse_pos, dest='start')
parser.add_argument('-E', '--stop-part', metavar='NPART', type=parse_pos, dest='stop')
parser.add_argument('mp4_output')
parser.add_argument('urls', nargs=2, help='On browser: devtools -> network -> copy url (take 2 links on googlevideo.com). One is the sound, the other the video (the order does not matter).')
args = parser.parse_args()


def url_sanitize(i) -> str:
  url = args.urls[i]
  try:
    return url[:url.index('&sq=')+4]
  except:
    print(f'bad url: {url}', file=sys.stderr)
    exit(1)

re_sq = re.compile(r'&sq=(\d+)')
def get_sq_time():
  m = re_sq.search(args.urls[0]) or re_sq.search(args.urls[1])
  try:
    return int(m.group(1)) * seconds_in_part
  except:
    print('no sq value in urls', file=sys.stderr)
    exit(2)

url0 = url_sanitize(0)
url1 = url_sanitize(1)

istart = args.start
istop = args.stop

if istart is None and istop is None:
  istart = 0
  istop = 2147483648

elif istart is None or istop is None:
  r = istart or istop
  if r[0]:
    t = get_sq_time()
    if r[0] == '@':
      if istart is None:
        istart = 0
        istop = t
      else:
        istart = t
        istop = 2147483648
    elif r[0] in ('-', '@-'):
      istart = t-r[1]
      istop = t
    else:
      istart = t
      istop = t+r[1]
  elif istart is None:
    istart = 0
    istop = istop[1]
  else:
    istart = istart[1]
    istop = 2147483648

elif not istart[0] and not istop[0]:
  istart = istart[1]
  istop = istop[1]
  if istop < istart:
    istart, istop = istop, istart

else:
  t = get_sq_time()

  def parse_relative(r):
    if not r[0]:
      return r[1]
    if r[0] == '@':
      return t
    elif r[0] == '@-':
      return t - r[1]
    elif r[0] == '@+':
      return t + r[1]

  t1 = parse_relative(istart)
  t2 = parse_relative(istop)

  if t1 is None:
    if t2 is not None:
      t = t2
    t1 = (t - istart[1]) if istart[0] == '-' else (t + istart[1])

  if t2 is None:
    t2 = (t1 - istop[1]) if istop[0] == '-' else (t1 + istop[1])

  istart = t1
  istop = t2
  if istop < istart:
    istart, istop = istop, istart

print(f'istart={istart}s istop={istop}s')

istart = istart // seconds_in_part
istop = (istop + seconds_in_part - 1) // seconds_in_part

print(f'partstart={istart} partstop={istop}')

filename_prefix:str = args.mp4_output
# remove suffix when mp4
if filename_prefix.endswith('.mp4'):
  filename_prefix = filename_prefix[:-4]

# (video, audio)
urls = (url0, url1) if url0[url0.index('&mime=') + 6] == 'v' else (url1, url0)

downloader = PartDownloader(filename_prefix, istart, istop)
filenames = downloader.start(*urls)

# wait for threads to start
sleep(2)

# merge audio and video
subprocess.run([
  'ffmpeg',
  '-i', filenames[0],
  '-i', filenames[1],
  '-c:v', 'copy',
  '-c:a', 'copy',
  filename_prefix + '.mp4'
])

downloader.join()

for filename in filenames:
  os.remove(filename)
