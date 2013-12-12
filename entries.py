import pickle, os, time
import subprocess, threading
import ctypes

from ctypes import byref

from win32api import *
try:
   from winxpgui import *
except ImportError:
   from win32gui import *
from win32gui_struct import *

import win32com.client

usr32 = ctypes.windll.user32


from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, pyqtSignal

class AbstractEntry(QtCore.QObject):
   def __init__(self):
      QtCore.QObject.__init__(self)
      self.icon = None
      self.loadedIconSize = 0
      self.label = u"Unknown abstract entry"
      self.totalTime = 0.
      self.entryType = u"Abstract"
      self.isHidden = False

class AppStarterEntry(AbstractEntry):
   ManualTracking = pyqtSignal(object)
   UpdateText = pyqtSignal()
   UpdateIcon = pyqtSignal()
   UpdateProfile = pyqtSignal()
   
   def __init__(self, path=None, parentWidget=None):
      AbstractEntry.__init__(self)
      self.parentWidget = parentWidget
      self.preferredIcon = 0
      self.cmdLineArgs = ""
      self.lastPlayed = 0. # seconds since the epoch
      self.running = False
      self.label = u"Unknown application"
      self.entryType = u"FireStarter"
      self.position = 0
      
      self.currentSessionTime = 0.
      
      if path is not None:
         head, tail = os.path.split(path)
         
         self.filename = path
         self.iconPath = path
         self.workingDir = head
         
         label = tail
         idx = tail.rfind('.')
         if idx>-1: label = label[:idx]
         self.label = label
         
   def ExportToFile(self, file):
      for s in (self.filename, self.workingDir, self.label, self.cmdLineArgs, self.iconPath):
         file.write(s)
         file.write('\n')
      pickle.dump(self.preferredIcon, file)
      pickle.dump(self.position, file)
      pickle.dump(self.totalTime, file)
   
   def ImportFromFile(self, file):
      self.filename = file.readline().strip()
      self.workingDir = file.readline().strip()
      self.label = file.readline().strip()
      self.cmdLineArgs = file.readline().strip()
      self.iconPath = file.readline().strip()
      #for string in [self.filename, self.workingDir, self.label]:
      #   string = file.readline().strip()
      self.preferredIcon = pickle.load(file)
      self.position = pickle.load(file)
      self.totalTime = pickle.load(file)
         
   def LoadIcon(self, iconSize=256):
      # No Icon
      if self.preferredIcon == -1:
         self.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
         return
      
      # Load Icon from local icon library
      elif self.preferredIcon == -2:
         self.icon=QtGui.QIcon(self.iconPath)
         return
      
      ###ELSE:
      # determine number of icons
      numIcons = win32gui.ExtractIconEx(self.iconPath, -1, 1)
      if(self.preferredIcon >= numIcons): self.preferredIcon = 0
      
      if (numIcons == 0):
         raise IOError("No icons found in file %s!"%self.iconPath)
         self.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
         return
      
      hIcon = ctypes.c_int()
      iconId = ctypes.c_int()
      
      # this is used instead of win32gui.ExtractIconEx because we need arbitrarily sized icons
      res = usr32.PrivateExtractIconsW(ctypes.c_wchar_p(self.iconPath), self.preferredIcon, iconSize,\
                                       iconSize, byref(hIcon), byref(iconId), 1, 0)
      if (res == 0):
         raise IOError("Could not extract %dx%dpx icon from file %s." % (iconSize, iconSize, self.iconPath))
         self.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
         return
      
      hIcon = hIcon.value # unpack c_int
      
      pm = QtGui.QPixmap.fromWinHICON(hIcon)
      DestroyIcon(hIcon)
   
      self.icon = QtGui.QIcon()
      self.icon.addPixmap(pm)
      self.loadedIconSize = iconSize
      
   def Run(self):
      if self.running:
         QtGui.QMessageBox.warning(self.parentWidget, "Warning","Application already running!")
         return
      
      prc = subprocess.Popen([self.filename, self.cmdLineArgs], shell=True, cwd=self.workingDir)
      self.running = True
      self.UpdateText.emit()
      
      svThread = threading.Thread(target=self.SuperviseProcess, args=(prc,))
      svThread.start()
      
   def SuperviseProcess(self, process):
      startTime = time.clock()
      
      # process supervising loop
      while(process.poll() is None):
         runtime = time.clock() - startTime
         self.currentSessionTime = runtime # atomic, threadsafe
         self.UpdateText.emit() # threadsafe
         
         time.sleep(2.)
      
      runtime = time.clock() - startTime
      
      if runtime < 10.:
         # program was probably started as another subprocess:
         self.ManualTracking.emit(self)
         
      self.totalTime += runtime
      self.lastPlayed = time.time()
      self.running = False
      
      self.UpdateProfile.emit()
      self.UpdateText.emit()
      return
   
class SteamEntry(AbstractEntry):
   def __init__(self, parentWidget=None):
      AbstractEntry.__init__(self)
      self.loadedIconSize = 32
      self.label = u"Unknown Steam application"
      self.entryType = u"Steam"
      self.isHidden = True
      self.appid = 0
      
   def ImportFromSteamGameStats(self, g):
      self.label = g.name
      self.totalTime = 60.*g.playtime
      self.iconFile = "%s_%s.jpg" % (g.appid, g.iconUrl)
      self.LoadIcon()
      self.appid = g.appid

   def LoadIcon(self, iconSize=32):
      iconPath = os.path.join("cache", "steam", "%s" % self.iconFile)
      
      if not os.path.isfile(iconPath):
         self.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
      else:
         self.icon=QtGui.QIcon(iconPath)