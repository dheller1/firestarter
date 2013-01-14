'''
Created on 03.01.2013

@author: heller
'''

import os, time
import ctypes
import pickle
import subprocess, threading

from ctypes import byref

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, pyqtSignal

from win32api import *
try:
   from winxpgui import *
except ImportError:
   from win32gui import *
from win32gui_struct import *

import win32com.client

usr32 = ctypes.windll.user32


class AppStarterEntry(QtCore.QObject):
   UpdateButton = pyqtSignal()
   UpdateProfile = pyqtSignal()
   
   def __init__(self, path=None, parentWidget=None):
      QtCore.QObject.__init__(self)
      self.icon = None
      self.loadedIconSize = 0
      self.parentWidget = parentWidget
      self.preferredIcon = 0
      self.cmdLineArgs = ""
      self.totalTime = 0.
      self.running = False
      self.label = "Unknown application"
      self.position = (0,0) # position in listwidget grid
      
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
      for s in (self.filename, self.workingDir, self.label, self.iconPath):
         file.write(s)
         file.write('\n')
      pickle.dump(self.preferredIcon, file)
      pickle.dump(self.position, file)
      pickle.dump(self.totalTime, file)
   
   def ImportFromFile(self, file):
      self.filename = file.readline().strip()
      self.workingDir = file.readline().strip()
      self.label = file.readline().strip()
      self.iconPath = file.readline().strip()
      #for string in [self.filename, self.workingDir, self.label]:
      #   string = file.readline().strip()
      self.preferredIcon = pickle.load(file)
      self.position = pickle.load(file)
      self.totalTime = pickle.load(file)
         
   def LoadIcon(self, iconSize=256):
      if self.preferredIcon < 0:
         self.icon=QtGui.QIcon("noicon.png")
         return
      
      # determine number of icons
      numIcons = win32gui.ExtractIconEx(self.iconPath, -1, 1)
      if(self.preferredIcon >= numIcons): self.preferredIcon = 0
      
      if (numIcons == 0):
         raise IOError("No icons found in file %s!"%self.iconPath)
         self.icon=QtGui.QIcon("noicon.png")
         return
      
      hIcon = ctypes.c_int()
      iconId = ctypes.c_int()
      
      # this is used instead of win32gui.ExtractIconEx because we need arbitrarily sized icons
      res = usr32.PrivateExtractIconsW(ctypes.c_wchar_p(self.iconPath), self.preferredIcon, iconSize,\
                                       iconSize, byref(hIcon), byref(iconId), 1, 0)
      if (res == 0):
         raise IOError("Could not extract %dx%dpx icon from file %s." % (iconSize, iconSize, self.iconPath))
         self.icon=QtGui.QIcon("noicon.png")
         return
      
      hIcon = hIcon.value # unpack c_int
      
      pm = QtGui.QPixmap.fromWinHICON(hIcon)
      DestroyIcon(hIcon)
   
      self.icon = QtGui.QIcon()
      self.icon.addPixmap(pm)
      self.iconSize = iconSize
      
   def Run(self):
      if self.running:
         QtGui.QMessageBox.warning(self.parentWidget, "Warning","Application already running!")
         return
      
      prc = subprocess.Popen([self.filename, self.cmdLineArgs], shell=True, cwd=self.workingDir)
      self.running = True
      self.UpdateButton.emit()
      
      svThread = threading.Thread(target=self.SuperviseProcess, name=self.label, args=(prc,))
      svThread.start()
      
   def SuperviseProcess(self, process):
      startTime = time.clock()
      
      process.wait()
      
      runtime = time.clock() - startTime
      
      self.totalTime += runtime
      self.running = False
      
      self.UpdateProfile.emit()
      self.UpdateButton.emit()
      return

class ChooseIconDialog(QtGui.QDialog):
   """ Dialog which loads icons from one or several files, displays them in a list widget, and allows to choose one of them.
       When called with exec_(), the call returns 'None' if Cancel was pressed, otherwise it returns a tuple of (filename,id)
       for the icon in 'filename' with id 'id'. """
   def __init__(self, parent=None, file=None, suggestions=False):
      QtGui.QDialog.__init__(self, parent)
      
      self.setWindowTitle("Choose icon:")
      self.resize(600,380)
      
      self.basefile = file
      
      # create widgets
      self.okBtn = QtGui.QPushButton("&Ok", self)
      self.okBtn.setDefault(True)
      self.okBtn.clicked.connect(self.accept)
      
      self.cancelBtn = QtGui.QPushButton("&Cancel", self)
      self.cancelBtn.clicked.connect(self.reject)
      
      self.selectFileBtn = QtGui.QPushButton("&Select file...", self)
      self.selectFileBtn.clicked.connect(self.SelectFile)
      
      self.countLabel = QtGui.QLabel("0 icons found.")
      
      size = QtCore.QSize(128,128)
      self.iconsList = QtGui.QListWidget(self)
      self.iconsList.setViewMode(QtGui.QListView.IconMode)
      self.iconsList.setIconSize(size)
      #self.iconsList.setGridSize(size)
      self.iconsList.setMovement(QtGui.QListView.Static)
      
      # init layout
      buttonsLayout= QtGui.QHBoxLayout()
      buttonsLayout.addWidget(self.okBtn)
      buttonsLayout.addWidget(self.cancelBtn)
      buttonsLayout.addWidget(self.selectFileBtn)
      buttonsLayout.addWidget(self.countLabel)
      
      
      mainLayout = QtGui.QVBoxLayout(self)
      
      if suggestions: mainLayout.addWidget(QtGui.QLabel("Suggested icons:"))
      mainLayout.addWidget(self.iconsList)
      mainLayout.addLayout(buttonsLayout)
      
      self.setLayout(mainLayout)
            
      # fill icon list
      self.Fill(file, suggestions)
      
   def exec_(self):
      result = QtGui.QDialog.exec_(self)
      
      if result == QtGui.QDialog.Accepted and len(self.iconsList.selectedItems())==1:
         icon = self.iconsList.selectedItems()[0]
         return icon.file, icon.id
      else: return None
      
   def AddIcons(self, file):
      iconSize = 256
      
      # determine number of icons in file
      numIcons = win32gui.ExtractIconEx(file, -1, 1)
      if (numIcons == 0): return 0
      
      for id in range(numIcons):
         # load icon
         hIcon = ctypes.c_int()
         iconId = ctypes.c_int()
         
         # this is used instead of win32gui.ExtractIconEx because we need arbitrarily sized icons
         res = usr32.PrivateExtractIconsW(ctypes.c_wchar_p(file), id, iconSize,\
                                          iconSize, byref(hIcon), byref(iconId), 1, 0)
         if (res == 0):
            raise IOError("Could not extract icon #%i from file %s." % (id+1, file))
            return
      
         hIcon = hIcon.value # unpack c_int
      
         pm = QtGui.QPixmap.fromWinHICON(hIcon)
         DestroyIcon(hIcon)
         
         icon = QtGui.QIcon()
         icon.addPixmap(pm)
         
         # add to list
         listEntry = QtGui.QListWidgetItem(self.iconsList)
         listEntry.setIcon(icon)
         listEntry.file = os.path.abspath(file)
         listEntry.id = id
         
      # return number of successfully loaded icons
      return id+1
         
   def Fill(self, file, suggestions=False):
      count = 0
      
      if not suggestions:
         count = self.AddIcons(file)
      else:
         for f in self.SuggestFiles(file):
            count += self.AddIcons(f)
         
      if count == 0:
         QtGui.QMessageBox.warning(self, "Warning", "No icons found! Please select one or more files with icons manually.")
         
      self.countLabel.setText("%i icon%s found." % (count, "" if count==1 else "s"))
      
   def FillList(self, files):
      count = 0
      for f in files:
         count += self.AddIcons(str(f)) # need to convert from QString to python string
      
      if count == 0:
         QtGui.QMessageBox.warning(self, "Warning", "No icons found! Please select one or more files with icons manually.")
         
      self.countLabel.setText("%i icon%s found." % (count, "" if count==1 else "s"))
      
   def SelectFile(self):
      files = QtGui.QFileDialog.getOpenFileNames(self, "Select icon file(s):", os.path.dirname(self.basefile) if self.basefile else ".",\
                                                 "Files containing icons (*.exe *.dll *.ico *.bmp)" )
      if len(files)>0:
         self.iconsList.clear()
         self.FillList(files)
         
   def SuggestFiles(self, file):
      files = []
      dir = os.path.dirname(file)
      dirList =  os.listdir(dir)
      
      for f in dirList:
         if os.path.join(dir,f) != file and (f.endswith(".exe") or f.endswith(".dll") or f.endswith(".ico") or f.endswith(".bmp")):
            files.append(os.path.join(dir,f))
            
      return files

#class EntryButton(QtGui.QToolButton):
#   def __init__(self, entry=None, parent=None, iconSize=48):
#      QtGui.QToolButton.__init__(self, parent)
#      
#      self.iconSize = iconSize
#      
#      # init button
#      self.setAutoRaise(True)
#      self.setIconSize(QtCore.QSize(self.iconSize,self.iconSize))
#      self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if self.iconSize > 16 else Qt.ToolButtonTextBesideIcon)
#      
#      # init menu
#      self.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
#      
#      if not entry: return
#      if entry.icon is not None: self.setIcon(entry.icon)
#      self.entry = entry
#      self.UpdateText()
#      
#      self.setMenu(EntryMenu(self.entry, self))
#      
#      self.clicked.connect(entry.Run)
#      self.entry.UpdateButton.connect(self.UpdateText)
#
#   def ChooseIcon(self):
#      dlg = ChooseIconDialog(self, file=self.entry.filename, suggestions=True)
#      result = dlg.exec_()
#      
#      if result == None: return
#      else:
#         path, id = result
#         self.entry.iconPath = path
#         self.entry.preferredIcon = id
#         self.entry.LoadIcon()
#         self.UpdateIcon()
#         self.entry.UpdateProfile.emit()
#
#   def Rename(self):
#      entry = self.entry
#      
#      text, accepted = QtGui.QInputDialog.getText(self, "Rename %s" % entry.label, "Please enter new name:", text=entry.label)
#      if accepted:
#         entry.label = text
#         self.UpdateText()
#         self.entry.UpdateProfile.emit()
#         
#   def UpdateIcon(self):
#      self.setIcon(self.entry.icon)
#      
#   def UpdateText(self):
#      entry = self.entry
#      if entry.running: timeText = "Currently running..."
#      else:
#         if entry.totalTime == 0.: timeText ="Never played"
#         elif entry.totalTime < 60.: timeText = "<1m played"
#         elif entry.totalTime < 20.*60: timeText = "%im %is played" % (entry.totalTime//60, entry.totalTime%60)
#         elif entry.totalTime < 60.*60: timeText = "%im played" % (entry.totalTime//60)
#         elif entry.totalTime < 20.*60*60: timeText = "%ih %im played" %  (entry.totalTime//3600, (entry.totalTime%3600)//60)
#         elif entry.totalTime < 200.*60*60: timeText = "%ih played" % (entry.totalTime//3600)
#         else: timeText = "%id %ih played" % (entry.totalTime//86400, (entry.totalTime%86400)//3600)
#      text = entry.label + "\n" + timeText
#      self.setText(text)
#      
class EntryListItem(QtGui.QListWidgetItem):
   def __init__(self, entry=None, parent=None, iconSize=48):
      QtGui.QListWidgetItem.__init__(self, parent)
      
      self.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
      
      self.iconSize = iconSize
      self.parent = parent
      
      # init icon
      #self.setAutoRaise(True)
      
      # this is done in parent list widget already
      #self.setIconSize(QtCore.QSize(self.iconSize,self.iconSize))
      #self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if self.iconSize > 16 else Qt.ToolButtonTextBesideIcon)
      
      # init menu
      #self.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
      
      if not entry: return
      if entry.icon is not None: self.setIcon(entry.icon)
      self.entry = entry
      self.UpdateText()
      
      #self.contextMenu = EntryMenu(self.entry, self.parent)
      
      #self.clicked.connect(entry.Run)
      self.entry.UpdateButton.connect(self.UpdateText)
      
   def parent(self):
      return self.parent if self.parent else None
      
   def UpdateIcon(self):
      self.setIcon(self.entry.icon)
      
   def UpdateText(self):
      entry = self.entry
      if entry.running: timeText = "Currently running..."
      else:
         if entry.totalTime == 0.: timeText ="Never played"
         elif entry.totalTime < 60.: timeText = "<1m played"
         elif entry.totalTime < 20.*60: timeText = "%im %is played" % (entry.totalTime//60, entry.totalTime%60)
         elif entry.totalTime < 60.*60: timeText = "%im played" % (entry.totalTime//60)
         elif entry.totalTime < 20.*60*60: timeText = "%ih %im played" %  (entry.totalTime//3600, (entry.totalTime%3600)//60)
         elif entry.totalTime < 200.*60*60: timeText = "%ih played" % (entry.totalTime//3600)
         else: timeText = "%id %ih played" % (entry.totalTime//86400, (entry.totalTime%86400)//3600)
      text = entry.label + "\n" + timeText
      self.setText(text)

class EntryMenu(QtGui.QMenu):
   def __init__(self, parent=None):
      QtGui.QMenu.__init__(self, parent)
      
      self.renameAction = QtGui.QAction("&Rename", self)
      self.chooseIconAction = QtGui.QAction("Choose &icon", self)
      self.removeAction = QtGui.QAction("&Delete", self)
      self.addAction(self.chooseIconAction)
      self.addAction(self.renameAction)
      self.addSeparator()
      self.addAction(self.removeAction)
      
      self.InitConnections()
      
   def InitConnections(self):
      if self.parent() is not None:
         self.chooseIconAction.triggered.connect(self.parent().ChooseIconForItem)
         self.renameAction.triggered.connect(self.parent().RenameItem)
         self.removeAction.triggered.connect(self.parent().RemoveItem)

class CategoryWidget(QtGui.QListWidget):
   ProfileChanged = pyqtSignal()
   
   def __init__(self, iconSize = 48):
      QtGui.QWidget.__init__(self)
      
      # layout/design initialization 
      self.iconSize = iconSize
      self.contextMenu = EntryMenu(self)
      
      size = QtCore.QSize(iconSize,iconSize)
      textSize = QtCore.QSize(0, 33)
      spacing = QtCore.QSize(20,20)
      
      self.setViewMode(QtGui.QListView.IconMode)
      self.setSpacing(20)
      self.setIconSize(size)
      self.setGridSize(size+textSize+spacing)
      self.setMovement(QtGui.QListView.Snap)
      #self.setResizeMode(QtGui.QListView.Adjust)
      
      self.setUniformItemSizes(True)
      
      self.clearSelection()
      
      style  = "QListView { background-image: url(wood-texture.jpg); color: white; background-attachment: fixed; }"\
             + "QListView::item { border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
      self.setStyleSheet(style)
      
      # connections
      self.itemDoubleClicked.connect(self.RunItem)

   def contextMenuEvent(self, e):
      lwitem = self.itemAt(e.pos())
      if lwitem is not None:
         self.contextMenu.exec_(e.globalPos())
         
   def dropEvent(self, e):
      QtGui.QListView.dropEvent(self, e)
      
      item = self.itemAt(e.pos())
      if item is not None:
         r = self.visualItemRect(item)
         newpos = (r.top()/self.gridSize().height(), r.left()/self.gridSize().width())
         if newpos != item.entry.position:
            item.entry.position = newpos
            self.ProfileChanged.emit()
         
   def mousePressEvent(self, e):
      if self.itemAt(e.pos()) is None:
         self.clearSelection()
         
      QtGui.QAbstractItemView.mousePressEvent(self, e)

   def AddEntry(self, entry):
      e = EntryListItem(entry=entry, parent=self, iconSize=self.iconSize)
      e.setSizeHint(self.gridSize())
      r = self.visualItemRect(e)
      pos = (r.top()/self.gridSize().height(), r.left()/self.gridSize().width())
      e.entry.position = pos
      
   def ChooseIconForItem(self):
      item = self.currentItem()
      if not item: return
      dlg = ChooseIconDialog(self, file=item.entry.filename, suggestions=True)
      result = dlg.exec_()
      
      if result == None: return
      else:
         path, id = result
         item.entry.iconPath = path
         item.entry.preferredIcon = id
         item.entry.LoadIcon()
         item.UpdateIcon()
         item.entry.UpdateProfile.emit()
         
   def RemoveItem(self):
      item = self.currentItem()
      if not item: return
      
      self.parent().RemoveItem(item.entry, self.row(item))

   def RenameItem(self):
      item = self.currentItem()
      if not item: return
      entry = item.entry
      
      text, accepted = QtGui.QInputDialog.getText(self, "Rename %s" % entry.label, "Please enter new name:", text=entry.label)
      if accepted:
         entry.label = text
         item.UpdateText()
         item.entry.UpdateProfile.emit()
         
   def RunItem(self,item):
      item.entry.Run()

class MainWidget(QtGui.QWidget):
   def __init__(self, parent=None):
      QtGui.QWidget.__init__(self, parent)
      
      self.setAcceptDrops(True)
      self.entries = []
      self.InitLayout()
      
   def dragEnterEvent(self, event):
      if (event.mimeData().hasUrls()):
         nonLocal = False
         for url in event.mimeData().urls():
            if(url.toLocalFile()==""): nonLocal=True
         
         if not nonLocal:
            event.acceptProposedAction()
      
   def dropEvent(self, event):
      for url in event.mimeData().urls():
         self.ParseUrl(url)
            
      event.acceptProposedAction()
      
   def AddEntry(self, entry):
      self.entries.append(entry)
      
      # send to child layouts
      for catWdg in self.catWidgets.values():
         catWdg.AddEntry(entry)
         
      entry.UpdateProfile.connect(self.parent().SaveProfile)
      
   def InitLayout(self):
      self.iconSize = 256
      self.setLayout(QtGui.QStackedLayout())
      
      self.catWidgets = {}
      self.catWidgetIndices = {}
      for iconSize in (16,32,48,128,256):
         wdg = CategoryWidget(iconSize)
         self.catWidgets[iconSize] = wdg
         self.catWidgetIndices[iconSize] = self.layout().addWidget(wdg)
         wdg.ProfileChanged.connect(self.parent().SaveProfile)
         
      self.layout().setCurrentIndex(self.catWidgetIndices[self.iconSize])
      
   def ParseUrl(self, url):
      file = unicode(url.toLocalFile())
      
      if (file == ""):
         QtGui.QMessageBox.critical(self, "Error", "Unable to parse filename.")
         return
      
      # walk down shortcuts
      while (file.endswith(".lnk")):
         shell = win32com.client.Dispatch("WScript.Shell")
         shortcut = shell.CreateShortCut(file)
         file = os.path.normpath(shortcut.Targetpath)
         if not os.path.exists(file):
            QtGui.QMessageBox.critical(self, "Error", "Could not find shortcut target '%s'. Broken link?" % file)
            return
      
      entry = AppStarterEntry(file, self)
      try:
         entry.LoadIcon(self.iconSize)
      except IOError:
         QtGui.QMessageBox.warning(self, "Warning", "No icon found in '%s.'" % file)
         entry.preferredIcon = -1
      
      self.AddEntry(entry)
      self.parent().SaveProfile()
      
   def RemoveItem(self, entry, row):
      msg = QtGui.QMessageBox(QtGui.QMessageBox.Warning, "Warning: Deleting entry", "Do you really want to remove this entry? All"+\
                              " information and playtime will be lost and can not be restored!", QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel, self)
      result = msg.exec_()
      if result == QtGui.QMessageBox.Cancel: return
      
      # find entry
      try:
         index = self.entries.index(entry)
      except ValueError:
         raise ValueError("Tried to remove entry from main widget's entry list, but it is not present!")
      
      # delete entry
      self.entries.pop(index)
      
      for wdg in self.catWidgets.values():
         i = wdg.takeItem(row)
         del i
      
      self.parent().SaveProfile()
         
   def SetIconSize(self, size):
      self.iconSize = size
      self.layout().setCurrentIndex(self.catWidgetIndices[size])

class MainWindow(QtGui.QMainWindow):
   def __init__(self):
      QtGui.QMainWindow.__init__(self)
      
      # UI initialization
      self.resize(800,600)
      self.setWindowTitle("FireStarter")
      self.setWindowIcon(QtGui.QIcon("fire.ico"))
      
      self.setCentralWidget(MainWidget(self))
      
      self.InitMenus()
      self.InitConnections()
      
      self.profile = os.environ.get("USERNAME")
      self.LoadProfile()
      
   def moveEvent(self, e):
      if e.oldPos() != e.pos():
         self.SaveProfile()
      
   def resizeEvent(self, e):
      # if using toolbars/dockwidgets later, be sure to take a look at QMainWindow::saveState / QSettings
      if e.oldSize() != e.size():
         updateProfile = True
         
      QtGui.QWidget.resizeEvent(self, e)
         
      if updateProfile:
         self.SaveProfile()
      
   def InitConnections(self):
      pass
   
   def InitMenus(self):
      self.settingsMenu = SettingsMenu(self, self.centralWidget().iconSize)
      self.menuBar().addMenu(self.settingsMenu)
      
   def LoadProfile(self, filename=None):
      if filename is None: filename = '%s.dat' % self.profile
      if not os.path.exists(filename): return
      
      with open(filename, 'r') as f:
         try:
            iconSize = pickle.load(f)
            numEntries = pickle.load(f)
            
            # restore window size and position
            size = pickle.load(f)
            self.resize(size[0], size[1])
            pos = pickle.load(f)
            self.move(pos[0],pos[1])
         except:
            QtGui.QMessageBox.critical(self, "Error", "Invalid profile '%s'!" % filename)
            return
         
         # set correct icon size
         try:
            self.settingsMenu.CheckIconSizeAction(iconSize)
            self.centralWidget().SetIconSize(iconSize)
         except ValueError: QtGui.QMessageBox(self, "Warning", "Invalid icon size in profile: %ix%ipx" %(iconSize,iconSize))
         
         for i in range(numEntries):
            entry = AppStarterEntry(parentWidget=self.centralWidget())
            try:
               entry.ImportFromFile(f)
               try:
                  entry.LoadIcon(256) # always load largest icon because otherwise we would scale up when increasing icon size at runtime
               except IOError: pass
               
               self.centralWidget().AddEntry(entry)
            except EOFError: QtGui.QMessageBox.critical(self, "Error", "Unable to load entry %i from profile '%s'!\nEntries might be incomplete." % (i+1, filename))
         
   def SaveProfile(self, filename=None):
      if filename is None: filename = '%s.dat' % self.profile
      
      #startTime = time.clock()
      with open(filename, 'w') as f:
         pickle.dump(self.centralWidget().iconSize, f)       # write preferred icon size 
         pickle.dump(len(self.centralWidget().entries), f)   # write number of entries
         pickle.dump( (self.size().width() , self.size().height() ), f) # write window size
         pickle.dump( (self.x(),self.y()), f)                # write window position
         for entry in self.centralWidget().entries:
            entry.ExportToFile(f)
         
         #print "Saved profile in %f seconds." % (time.clock() - startTime)

   def UpdateIconSizeFromMenu(self):
      # determine new icon size
      curAction = self.settingsMenu.iconSizeActions.checkedAction().text()
      size = int(curAction.split('x')[0])
      self.centralWidget().SetIconSize(size)
      
      self.SaveProfile()

class SettingsMenu(QtGui.QMenu):
   def __init__(self, parent=None, iconSize=48):
      QtGui.QMenu.__init__(self, "&Settings", parent)
      
      # icon sizes
      iconSizes = self.addMenu("&Icon size...")
      self.iconSizeActions = QtGui.QActionGroup(iconSizes)
      
      for size in (16,32,48,128,256):
         act = QtGui.QAction("%ix%i" %(size, size), iconSizes)
         act.setCheckable(True)
         if size == iconSize: act.setChecked(True)
         self.iconSizeActions.addAction(act)
         iconSizes.addAction(act)
         
      # profiles
      self.profileMenu = self.addMenu(ProfileMenu(self))
      
      self.InitConnections()
   
   def CheckIconSizeAction(self, size):
      found = False
      for act in self.iconSizeActions.actions():
         if act.text() == "%ix%i" % (size,size):
            act.setChecked(True)
            found = True
         else: act.setChecked(False)
      
      if not found:
         raise ValueError('Tried to select unsupported icon size in settings menu: %ix%ipx' %(size,size))
   
   def InitConnections(self):
      self.iconSizeActions.triggered.connect(self.parent().UpdateIconSizeFromMenu)
      
class ProfileMenu(QtGui.QMenu):
   def __init__(self, parent=None):
      QtGui.QMenu.__init__(self, "Switch &profile", parent)
      
      profiles = QtGui.QActionGroup(self)
      
      files = os.listdir(".")
      for f in files:
         if f.endswith(".dat"):
            act = QtGui.QAction(f, profiles)
            if f.startswith(os.environ.get("USERNAME")):
               act.setChecked(True)
               print f
            profiles.addAction(act)
            self.addAction(act)
