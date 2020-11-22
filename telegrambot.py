import threading
import glob
import time
import random
import datetime
import telepot
import os
from os import path
from pprint import pprint
from telepot.loop import MessageLoop
import urllib.request
import time
import digitalio
import board
from PIL import Image, ImageOps
import numpy  # pylint: disable=unused-import
import adafruit_rgb_display.st7789 as st7789
import ffmpy
import json

# ffmpy requires ffmpeg installed as well
# telepot is telegram's bot library

with open('config.json') as f:
  config = json.load(f)

botToken = config["telegramBotToken"]
clients = config["clients"]

# Change to match your display
BUTTON_NEXT = board.D23
BUTTON_PREVIOUS = board.D24

# Configuration for CS and DC pins (these are PiTFT defaults):
cs_pin = digitalio.DigitalInOut(board.CE0)
dc_pin = digitalio.DigitalInOut(board.D25)

# Set this to None on the Mini PiTFT
reset_pin = None

# Config for display baudrate (default max is 64mhz):
BAUDRATE = 64000000

def init_button(pin):
    button = digitalio.DigitalInOut(pin)
    button.switch_to_input()
    button.pull = digitalio.Pull.UP
    return button


# pylint: disable=too-few-public-methods
class Frame:
    def __init__(self, duration=0):
        self.duration = duration
        self.image = None
  
class AnimatedGif:
  def __init__(self, display, botToken, clients, width=None, height=None, folder=None):
    self._frame_count = 0
    self._frames = []
    self._botToken = botToken
    self._clients = clients
    self._currentInd = 0
    self.lock = threading.Lock()
    
    if width is not None:
      self._width = width
    else:
      self._width = display.width
    if height is not None:
      self._height = height
    else:
      self._height = display.height
    self.display = display
    self.advance_button = init_button(BUTTON_NEXT)
    self.back_button = init_button(BUTTON_PREVIOUS)
    
  # gets the max image system knows
  def getInd(self):
    if (path.exists("imageindex.txt")):
      f = open("imageindex.txt","r")
      imgInd = int(f.read())
      return imgInd
    return 0
  
  # updates the total number of images system knows
  def writeInd(self, ind):
    f = open("imageindex.txt","w")
    f.write(str(ind))
    f.close()

  # downloads a media file to disk, if it's an mp4 converts with ffmpeg
  def downloadFile(self, file):
    filePath = file['file_path']
    fileName, fileExtension = path.splitext(filePath)
    imgInd = self.getInd()
    imgInd += 1
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{botToken}/{filePath}", f"image{imgInd}{fileExtension}")
    print (f"saved image{imgInd}{fileExtension}")
    if (fileExtension == ".mp4"):
      print (f"Converting video to gif: image{imgInd}.gif")
      ff = ffmpy.FFmpeg(inputs={f'image{imgInd}{fileExtension}': None}, outputs={f'image{imgInd}.gif': '-vf scale=w=240:h=240:force_original_aspect_ratio=decrease'} )
      ff.run()
      os.remove(f'image{imgInd}{fileExtension}')
    self.writeInd(imgInd)
    self.loadImage(imgInd)
  
  # handles telegram message
  def handle(self, msg):
    from_id = msg['from']['id']
    if (from_id not in clients):
      print ("I DON'T KNOW %s with id %s", msg['from']['first_name'], from_id)
      return
    if ('photo' in msg):
      print ("Found photos")
      file = bot.getFile(msg['photo'][0]['file_id'])
      self.downloadFile(file)
      bot.sendMessage(msg['chat']['id'], f"{msg['chat']['first_name']}, I got the image.")
    elif ('animation' in msg):
      print ("found GIF")
      pprint(msg)
      file = bot.getFile(msg['animation']['file_id'])
      self.downloadFile(file)
      bot.sendMessage(msg['chat']['id'], f"{msg['chat']['first_name']}, I got the animation.")
    else:
      print ("IDK?")
      pprint(msg)
      bot.sendMessage(msg['chat']['id'], f"{msg['chat']['first_name']}, I don't know what to do with this.")
  
  # forward button
  def advance(self):
    ind = self.getInd()
    new = (self._currentInd + 1)  % ind
    print(new)
    self.loadImage(new)
  
  # back button
  def back(self):
    ind = self.getInd()
    new = (ind + self._currentInd - 1)  % ind
    print(new)
    self.loadImage(new)
    
  # loads gif and jpgs into _frames list
  def loadImage(self, ind):
    ind = int(ind)
    self._currentInd = ind
    imageList = glob.glob(f"image{ind}.*")
    if (not imageList):
      return
    print (f"Loading: {imageList[0]}")
    self.lock.acquire()
    try:
      if (imageList):
        image = Image.open(imageList[0])
        duration = 0
        self._frames.clear()
        if ('jfif' in image.info):
          #jpg
          duration = 5000
          self._frame_count = 1
          frame_object = Frame(duration=duration)
          frame_object.image = ImageOps.pad(  # pylint: disable=no-member
            image.convert("RGB"),
            (self._width, self._height),
            method=Image.NEAREST,
            color=(0, 0, 0),
            centering=(0.5, 0.5),
          )
          self._frames.append(frame_object)
        else:
          if "duration" in image.info:
            duration = image.info["duration"]
          self._frame_count = image.n_frames
          for frame in range(self._frame_count):
            image.seek(frame)
            # Create blank image for drawing.
            # Make sure to create image with mode 'RGB' for full color.
            frame_object = Frame(duration=duration)
            frame_object.image = ImageOps.pad(  # pylint: disable=no-member
              image.convert("RGB"),
              (self._width, self._height),
              method=Image.NEAREST,
              color=(0, 0, 0),
              centering=(0.5, 0.5),
            )
            self._frames.append(frame_object)
    finally:
      self.lock.release()
  
  # a thread to handleanimation
  def play(self):
    while True:
      # not sure if this is any use, python gods let me know.
      self.lock.acquire()
      frames = self._frames.copy()
      self.lock.release()
      if (not frames):
        print("cant find frames")
        time.sleep(1)
      for frame_object in frames:
        start_time = time.monotonic()
        self.display.image(frame_object.image)
        self.display.
        while time.monotonic() < (start_time + frame_object.duration/1000):
          pass
  
  # another thread to handle button presses
  def buttons(self):
    while True:
      if not self.advance_button.value:
        print('advance')
        self.advance()
      if not self.back_button.value:
        print('back')
        self.back()

# Setup SPI bus using hardware SPI:
spi = board.SPI()

disp = st7789.ST7789(
  spi,
  height=240, y_offset=80,
  rotation=0,
  cs=cs_pin,
  dc=dc_pin,
  baudrate=BAUDRATE,
)


gif_player = AnimatedGif(disp, botToken, clients, width=disp.width, height=disp.height, folder=".")
ind = gif_player.getInd()
gif_player.loadImage(ind)

bot = telepot.Bot(botToken)
MessageLoop(bot, gif_player.handle).run_as_thread()
print ('I am listening ...')

t = threading.Thread(target=gif_player.play)
t.start()

t2 = threading.Thread(target=gif_player.buttons)
t2.start()

while 1:
  time.sleep(10)