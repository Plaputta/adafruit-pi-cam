import atexit
import errno
import fnmatch
import io
import os
import os.path
import picamera
import pygame
import stat
import threading
import time
import yuv2rgb
from ft5406 import Touchscreen, TS_PRESS, TS_RELEASE, TS_MOVE
from pygame.locals import *


class Icon:

	def __init__(self, name):
	  self.name = name
	  try:
	    self.bitmap = pygame.image.load(iconPath + '/' + name + '.png')
	  except:
	    pass

class Button:

	def __init__(self, rect, **kwargs):
	  self.rect     = rect # Bounds
	  self.color    = None # Background fill color, if any
	  self.iconBg   = None # Background Icon (atop color fill)
	  self.iconFg   = None # Foreground Icon (atop background)
	  self.bg       = None # Background Icon name
	  self.fg       = None # Foreground Icon name
	  self.callback = None # Callback function
	  self.value    = None # Value passed to callback
	  for key, value in kwargs.items():
	    if   key == 'color': self.color    = value
	    elif key == 'bg'   : self.bg       = value
	    elif key == 'fg'   : self.fg       = value
	    elif key == 'cb'   : self.callback = value
	    elif key == 'value': self.value    = value

	def selected(self, x, y):
	  x1 = self.rect[0]
	  y1 = self.rect[1]
	  x2 = x1 + self.rect[2] - 1
	  y2 = y1 + self.rect[3] - 1
	  if ((x >= x1) and (x <= x2) and
	      (y >= y1) and (y <= y2)):
	    if self.callback:
	      if self.value is None: self.callback()
	      else:                  self.callback(self.value)
	    return True
	  return False

	def draw(self, screen):
	  if self.color:
	    screen.fill(self.color, self.rect)
	  if self.iconBg:
	    screen.blit(self.iconBg.bitmap,
	      (self.rect[0]+(self.rect[2]-self.iconBg.bitmap.get_width())/2,
	       self.rect[1]+(self.rect[3]-self.iconBg.bitmap.get_height())/2))
	  if self.iconFg:
	    screen.blit(self.iconFg.bitmap,
	      (self.rect[0]+(self.rect[2]-self.iconFg.bitmap.get_width())/2,
	       self.rect[1]+(self.rect[3]-self.iconFg.bitmap.get_height())/2))

	def setBg(self, name):
	  if name is None:
	    self.iconBg = None
	  else:
	    for i in icons:
	      if name == i.name:
	        self.iconBg = i
	        break

def viewCallback(n): # Viewfinder buttons
	global loadIdx, scaled, screenMode, screenModePrior, settingMode, storeMode

	if n is 0:   # Gear icon (settings)
	  takePicture()
	elif n is 1: # Play icon (image playback)
	  if scaled: # Last photo is already memory-resident
	    loadIdx         = saveIdx
	    screenMode      =  0 # Image playback
	    screenModePrior = -1 # Force screen refresh
	  else:      # Load image
	    r = imgRange(pathData[storeMode])
	    if r: showImage(r[1]) # Show last image in directory
	    else: screenMode = 2  # No images

def doneCallback(): # Exit settings
	global screenMode, settingMode
	if screenMode > 3:
	  settingMode = screenMode
	screenMode = 3 # Switch back to viewfinder mode

def imageCallback(n): # Pass 1 (next image), -1 (prev image) or 0 (delete)
	global screenMode
	if n is 0:
	  screenMode = 1 # Delete confirmation
	else:
	  showNextImage(n)

def deleteCallback(n): # Delete confirmation
	global loadIdx, scaled, screenMode, storeMode
	screenMode      =  0
	screenModePrior = -1
	if n is True:
	  os.remove(pathData[storeMode] + '/IMG_' + '%04d' % loadIdx + '.JPG')
	  if(imgRange(pathData[storeMode])):
	    screen.fill(0)
	    pygame.display.update()
	    showNextImage(-1)
	  else: # Last image deleteted; go to 'no images' mode
	    screenMode = 2
	    scaled     = None
	    loadIdx    = -1

# Global stuff -------------------------------------------------------------

screenMode      =  3      # Current screen mode; default = viewfinder
screenModePrior = -1      # Prior screen mode (for detecting changes)
settingMode     =  0      # Last-used settings mode (default = storage)
storeMode       =  0      # Storage mode; default = Photos folder
storeModePrior  = -1      # Prior storage mode (for detecting changes)
sizeMode        =  0      # Image size; default = Large
fxMode          =  0      # Image effect; default = Normal
isoMode         =  0      # ISO settingl default = Auto
iconPath        = 'icons' # Subdirectory containing UI bitmaps (PNG format)
saveIdx         = -1      # Image index for saving (-1 = none set yet)
loadIdx         = -1      # Image index for loading
scaled          = None    # pygame Surface w/last-loaded image

sizeData = [ # Camera parameters for different size settings
 # Full res      Viewfinder  Crop window
 [(2592, 1944), (800, 480), (0.0   , 0.0   , 1.0   , 1.0   )], # Large
 [(1920, 1080), (800, 480), (0.1296, 0.2222, 0.7408, 0.5556)], # Med
 [(1440, 1080), (800, 480), (0.2222, 0.2222, 0.5556, 0.5556)]] # Small

pathData = [
  '/home/pi/Photos',     # Path for storeMode = 0 (Photos folder)
  '/boot/DCIM/CANON999', # Path for storeMode = 1 (Boot partition)
  '/home/pi/Photos']     # Path for storeMode = 2 (Dropbox)

icons = [] # This list gets populated at startup

# buttons[] is a list of lists; each top-level list element corresponds
# to one screen mode (e.g. viewfinder, image playback, storage settings),
# and each element within those lists corresponds to one UI button.
# There's a little bit of repetition (e.g. prev/next buttons are
# declared for each settings screen, rather than a single reusable
# set); trying to reuse those few elements just made for an ugly
# tangle of code elsewhere.

buttons = [
  # Screen mode 0 is photo playback
  [Button((  200,408,400, 52), bg='done' , cb=doneCallback),
   Button((  20,  20, 80, 52), bg='prev' , cb=imageCallback, value=-1),
   Button((700,  20, 80, 52), bg='next' , cb=imageCallback, value= 1),
   Button(( 322, 189,157,102)), # 'Working' label (when enabled)
   Button((389,229, 22, 22)), # Spinner (when enabled)
   Button((361,  20, 78, 52), bg='trash', cb=imageCallback, value= 0)],

  # Screen mode 1 is delete confirmation
  [Button((  0,140,800, 33), bg='delete'),
   Button(( 270,190,120,100), bg='yn', fg='yes',
    cb=deleteCallback, value=True),
   Button((410,190,120,100), bg='yn', fg='no',
    cb=deleteCallback, value=False)],

  # Screen mode 2 is 'No Images'
  [Button((0,  0,800,480), cb=doneCallback), # Full screen = button
   Button((240,275,320, 52), bg='done'),       # Fake 'Done' button
   Button((240, 140,320, 80), bg='empty')],     # 'Empty' message

  # Screen mode 3 is viewfinder / snapshot
  [Button((  20,408,156, 52), bg='gear', cb=viewCallback, value=0),
   Button((624,408,156, 52), bg='play', cb=viewCallback, value=1),
   Button((322, 189, 157, 102)),  # 'Working' label (when enabled)
   Button((389, 229, 22, 22))]  # Spinner (when enabled)

]


# Assorted utility functions -----------------------------------------------


# Scan files in a directory, locating JPEGs with names matching the
# software's convention (IMG_XXXX.JPG), returning a tuple with the
# lowest and highest indices (or None if no matching files).
def imgRange(path):
	min = 9999
	max = 0
	try:
	  for file in os.listdir(path):
	    if fnmatch.fnmatch(file, 'IMG_[0-9][0-9][0-9][0-9].JPG'):
	      i = int(file[4:8])
	      if(i < min): min = i
	      if(i > max): max = i
	finally:
	  return None if min > max else (min, max)

# Busy indicator.  To use, run in separate thread, set global 'busy'
# to False when done.
def spinner():
	global busy, screenMode, screenModePrior

	buttons[screenMode][3].setBg('working')
	buttons[screenMode][3].draw(screen)
	pygame.display.update()

	busy = True
	n    = 0
	while busy is True:
	  pygame.display.update()
	  n = (n + 1) % 5
	  time.sleep(0.15)

	buttons[screenMode][3].setBg(None)
	screenModePrior = -1 # Force refresh

def takePicture():
	global busy, gid, loadIdx, saveIdx, scaled, sizeMode, storeMode, storeModePrior, uid

	if not os.path.isdir(pathData[storeMode]):
	  try:
	    os.makedirs(pathData[storeMode])
	    # Set new directory ownership to pi user, mode to 755
	    os.chown(pathData[storeMode], uid, gid)
	    os.chmod(pathData[storeMode],
	      stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
	      stat.S_IRGRP | stat.S_IXGRP |
	      stat.S_IROTH | stat.S_IXOTH)
	  except OSError as e:
	    # errno = 2 if can't create folder
	    print(errno.errorcode[e.errno])
	    return

	# If this is the first time accessing this directory,
	# scan for the max image index, start at next pos.
	if storeMode != storeModePrior:
	  r = imgRange(pathData[storeMode])
	  if r is None:
	    saveIdx = 1
	  else:
	    saveIdx = r[1] + 1
	    if saveIdx > 9999: saveIdx = 0
	  storeModePrior = storeMode

	# Scan for next available image slot
	while True:
	  filename = pathData[storeMode] + '/IMG_' + '%04d' % saveIdx + '.JPG'
	  if not os.path.isfile(filename): break
	  saveIdx += 1
	  if saveIdx > 9999: saveIdx = 0

	t = threading.Thread(target=spinner)
	t.start()

	scaled = None
	camera.resolution = sizeData[sizeMode][0]
	camera.crop       = sizeData[sizeMode][2]
	try:
	  camera.capture(filename, use_video_port=False, format='jpeg',
	    thumbnail=None)
	  # Set image file ownership to pi user, mode to 644
	  # os.chown(filename, uid, gid) # Not working, why?
	  os.chmod(filename,
	    stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
	  img    = pygame.image.load(filename)
	  scaled = pygame.transform.scale(img, sizeData[sizeMode][1])

	finally:
	  # Add error handling/indicator (disk full, etc.)
	  camera.resolution = sizeData[sizeMode][1]
	  camera.crop       = (0.0, 0.0, 1.0, 1.0)

	busy = False
	t.join()

	if scaled:
	  if scaled.get_height() < 480: # Letterbox
	    screen.fill(0)
	  screen.blit(scaled,
	    ((800 - scaled.get_width() ) / 2,
	     (480 - scaled.get_height()) / 2))
	  pygame.display.update()
	  time.sleep(2.5)
	  loadIdx = saveIdx

def showNextImage(direction):
	global busy, loadIdx

	t = threading.Thread(target=spinner)
	t.start()

	n = loadIdx
	while True:
	  n += direction
	  if(n > 9999): n = 0
	  elif(n < 0):  n = 9999
	  if os.path.exists(pathData[storeMode]+'/IMG_'+'%04d'%n+'.JPG'):
	    showImage(n)
	    break

	busy = False
	t.join()

def showImage(n):
	global busy, loadIdx, scaled, screenMode, screenModePrior, sizeMode, storeMode

	t = threading.Thread(target=spinner)
	t.start()

	img      = pygame.image.load(
	            pathData[storeMode] + '/IMG_' + '%04d' % n + '.JPG')
	scaled   = pygame.transform.scale(img, sizeData[sizeMode][1])
	loadIdx  = n

	busy = False
	t.join()

	screenMode      =  0 # Photo playback
	screenModePrior = -1 # Force screen refresh


def Kill(channel):
  os.system("sudo pkill gvfs")
  pygame.quit()

# Initialization -----------------------------------------------------------

# Init framebuffer/touchscreen environment variables
os.system("sudo pkill gvfs")
os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"

# Get user & group IDs for file & folder creation
# (Want these to be 'pi' or other user, not root)
s = os.getenv("SUDO_UID")
uid = int(s) if s else os.getuid()
s = os.getenv("SUDO_GID")
gid = int(s) if s else os.getgid()

# Buffers for viewfinder data
rgb = bytearray(800 * 480 * 3)
yuv = bytearray(576000) #800 * 480 * 3 / 2

# Init pygame and screen
pygame.init()
screen = pygame.display.set_mode((800,480),pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

ts = Touchscreen()

# Init camera and set up default values
camera            = picamera.PiCamera()
atexit.register(camera.close)
camera.resolution = sizeData[sizeMode][1]
#camera.crop       = sizeData[sizeMode][2]
camera.crop       = (0.0, 0.0, 1.0, 1.0)
camera.vflip = True
# Leave raw format at default YUV, don't touch, don't set to RGB!

# Load all icons at startup.
for file in os.listdir(iconPath):
  if fnmatch.fnmatch(file, '*.png'):
    icons.append(Icon(file.split('.')[0]))

# Assign Icons to Buttons, now that they're loaded
for s in buttons:        # For each screenful of buttons...
  for b in s:            #  For each button on screen...
    for i in icons:      #   For each icon...
      if b.bg == i.name: #    Compare names; match?
        b.iconBg = i     #     Assign Icon to Button
        b.bg     = None  #     Name no longer used; allow garbage collection
      if b.fg == i.name:
        b.iconFg = i
        b.fg     = None


def touch_handler(event, touch):
  global processingTouch, queuedTouch
  if processingTouch: return
  if event == TS_PRESS:
    if touch.valid:
      queuedTouch = [touch.x, touch.y]

      #for b in buttons[screenMode]:
      #  if b.selected(touch.x, touch.y): break

for touch in ts.touches:
  touch.on_press = touch_handler
  touch.on_release = touch_handler
  touch.on_move = touch_handler

ts.run()

pygame.font.init() # you have to call this at the start,
                   # if you want to use this module.
myfont = pygame.font.SysFont('Comic Sans MS', 30)

# Main loop ----------------------------------------------------------------
global processingTouch, queuedTouch

processingTouch = False
queuedTouch = [-1,-1]

while True:
    # Redraw Code etc
    for event in pygame.event.get():
      if event.type == pygame.QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
        ts.stop()
        Kill(0)

    if not processingTouch:

      if queuedTouch[0] >= 0:
        processingTouch = True
        time.sleep(0.5)
        textsurface = myfont.render('Some Text', False, (255, 255, 255))
        screen.fill(0)
        screen.blit(textsurface, (0, 0))
        pygame.display.update()
        time.sleep(2.5)
        queuedTouch = [-1,-1]
        processingTouch = False


      if screenMode == 3:  # Viewfinder mode
        stream = io.BytesIO()  # Capture into in-memory stream
        camera.capture(stream, use_video_port=True, format='raw')
        stream.seek(0)
        stream.readinto(yuv)  # stream -> YUV buffer
        stream.close()
        yuv2rgb.convert(yuv, rgb, sizeData[sizeMode][1][0],
                        sizeData[sizeMode][1][1])
        img = pygame.image.frombuffer(rgb[0:
                                          (sizeData[sizeMode][1][0] * sizeData[sizeMode][1][1] * 3)],
                                      sizeData[sizeMode][1], 'RGB')
      elif screenMode < 2:  # Playback mode or delete confirmation
        img = scaled  # Show last-loaded image
      else:  # 'No Photos' mode
        img = None  # You get nothing, good day sir

      if img is None or img.get_height() < 480:  # Letterbox, clear background
        screen.fill(0)
      if img:
        screen.blit(img,
                    ((800 - img.get_width()) / 2,
                     (480 - img.get_height()) / 2))

      for i, b in enumerate(buttons[screenMode]):
        b.draw(screen)
      pygame.display.update()

    try:
        pass
    except KeyboardInterrupt:
        ts.stop()
        Kill(0)
