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

re_time = re.compile(r'^(?:(?:(\d+):)?(\d+):)?(\d+)$')
def parse_time(s):
  m = re_time.match(s)
  try:
    hours = m.group(1)
    hours = int(hours) if hours else 0
    minutes = m.group(2)
    minutes = int(minutes) if minutes else 0
    return hours * 3600 + minutes * 60 + int(m.group(3))
  except Exception as e:
    raise ValueError()

def parse_duration(s):
  return (0, parse_time(s))

def parse_to(s):
  return (1, parse_time(s))

def parse_pos(s):
  return int(s) * 5

def parse_pos_duration(s):
  return (0, int(s)*5)

def parse_pos_to(s):
  return (1, int(s)*5)


parser = argparse.ArgumentParser(
  formatter_class=argparse.RawDescriptionHelpFormatter,
  description='Youtube live stream downloader (https://github.com/jonathanpoelen/youtube-live-stream-dl).\nDownload parts from the Youtube Video that is live streamed, from start of the stream till the end.',
  epilog="Time format: [[HH:]MM:]SS\n  HH expresses the number of hours, MM the number of minutes and, SS the number of seconds.")
parser.add_argument('-s', '--start', metavar='TIME', type=parse_time, default=0)
parser.add_argument('-t', '--stop', metavar='TIME', type=parse_to)
parser.add_argument('-d', '--duration', metavar='TIME', type=parse_duration, dest='stop')
parser.add_argument('-S', '--start-part', metavar='NPART', type=parse_pos, dest='start')
parser.add_argument('-T', '--stop-part', metavar='NPART', type=parse_pos_to, dest='stop')
parser.add_argument('-D', '--duration-part', metavar='NPART', type=parse_pos_duration, dest='stop')
parser.add_argument('mp4_output')
parser.add_argument('urls', nargs=2, help='On browser: devtools -> network -> copy url (take 2 links on googlevideo.com)')
args = parser.parse_args()

# each part should be equivalent to 5 seconds of video
istart = args.start // 5
if args.stop is None:
  istop = 2147483648
elif args.stop[0] == 1:
  istop = (args.stop[1] + 4) // 5
else:
  istop = (args.start + args.stop[1] + 4) // 5

filename_prefix:str = args.mp4_output
# remove suffix when mp4
if filename_prefix.endswith('.mp4'):
  filename_prefix = filename_prefix[:-4]

def url_sanitize(i) -> str:
  url = args.urls[i]
  try:
    return url[:url.find('&sq=')+4]
  except:
    print(f'bad url: {url}', file=sys.stderr)
    exit(1)

url0 = url_sanitize(0)
url1 = url_sanitize(1)

# (video, audio)
urls = (url0, url1) if url0[url0.find('&mime=') + 6] == 'v' else (url1, url0)

downloader = PartDownloader(filename_prefix, istart, istop)
filenames = downloader.start(*urls)

print(istart, istop, filenames)
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
