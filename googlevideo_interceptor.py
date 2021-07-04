# use https://github.com/jonathanpoelen/qwebdriver
# this intercept googlevideo url of youtube

from qwebdriver.webdriver import AppDriver
import sys

app = AppDriver(headless=True, logger=True)

class Interceptor:
  video = None
  audio = None
  def url_interceptor(self, url):
    if '.googlevideo.com/' in url:
      if '&mime=audio' in url:
        self.audio = url
      elif '&mime=video' in url:
        self.video = url

def run(driver):
  driver.set_url_request_interceptor(sys.argv[1])
  driver.get('https://www.youtube.com/watch?v=cKw79MI2ZLc')
  driver.execute_script('''
    const ev = document.createEvent('Events');
    ev.initEvent('click', true, false);
    document.getElementsByTagName('button')[0].dispatchEvent(ev);
  ''')
  driver.execute_script('''
    const ev = document.createEvent('Events');
    ev.initEvent('click', true, false);
    const elems = document.getElementsByClassName('ytp-cued-thumbnail-overlay-image');
    console.log(elems);
    elems[0].dispatchEvent(ev);
    return true
  ''', False)
  interceptor = Interceptor()
  while not driver.sleep_ms(1000) and not (interceptor.audio and interceptor.video):
    driver.sleep_ms(1000)
    break
  app.quit()
  print(interceptor.audio)
  print(interceptor.video)
app.run(run)
