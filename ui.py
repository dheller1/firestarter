'''
Created on 03.01.2013

@author: heller
'''

import os, time
import ctypes
import pickle
import subprocess, threading
import shutil

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

from widgets import IconSizeComboBox
from dialogs import ChooseIconDialog, EntryPropertiesDialog


class AppStarterEntry(QtCore.QObject):
   UpdateText = pyqtSignal()
   UpdateIcon = pyqtSignal()
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
      self.UpdateText.emit()
      
      svThread = threading.Thread(target=self.SuperviseProcess, name=self.label, args=(prc,))
      svThread.start()
      
   def SuperviseProcess(self, process):
      startTime = time.clock()
      
      process.wait()
      
      runtime = time.clock() - startTime
      
      self.totalTime += runtime
      self.running = False
      
      self.UpdateProfile.emit()
      self.UpdateText.emit()
      return


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
#      self.entry.UpdateText.connect(self.UpdateText)
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

#class EntryListTItem(QtGui.QTableWidgetItem):
#   def __init__(self, entry=None, parent=None, iconSize=48):
#      QtGui.QTableWidgetItem.__init__(self)
#      
#      self.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
#      
#      self.iconSize = iconSize
#      self.parent = parent
#      
#      if not entry: return
#      if entry.icon is not None: self.setIcon(entry.icon)
#      self.entry = entry
#      self.UpdateText()
#      
#      self.entry.UpdateText.connect(self.UpdateText)
#      
#   def parent(self):
#      return self.parent if self.parent else None
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
      
class EntryItem(QtGui.QListWidgetItem):
   """ Base class for entry items, independent of whether they are in list or icon view mode """
   def __init__(self, entry=None, parent=None, iconSize=48):
      QtGui.QListWidgetItem.__init__(self, parent)
      
      self.iconSize = iconSize
      self.parent = parent
      
      if not entry: return
      if entry.icon is not None: self.setIcon(entry.icon)
      self.entry = entry
      self.UpdateText()
      
      self.entry.UpdateText.connect(self.UpdateText)
      self.entry.UpdateIcon.connect(self.UpdateIcon)
      
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
      text = entry.label + ("\n" + timeText if self.showPlaytime else "")
      self.setText(text)
      
class EntryListItem(EntryItem):
   """ Specific entry item for list view """
   def __init__(self, entry=None, parent=None, iconSize=48):
      self.showPlaytime = False
      
      EntryItem.__init__(self, entry, parent, iconSize)
      self.setTextAlignment(QtCore.Qt.AlignLeft)
      
class EntryIconItem(EntryItem):
   """ Specific entry item for icon view """
   def __init__(self, entry=None, parent=None, iconSize=48):
      self.showPlaytime = True
      
      EntryItem.__init__(self, entry, parent, iconSize)
      self.setTextAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
      
class EntryMenu(QtGui.QMenu):
   def __init__(self, parent=None):
      QtGui.QMenu.__init__(self, parent)
      
      self.renameAction = QtGui.QAction("&Rename", self)
      self.chooseIconAction = QtGui.QAction("Choose &icon", self)
      self.propertiesAction = QtGui.QAction("&Properties", self)
      self.removeAction = QtGui.QAction("&Delete", self)
      self.addAction(self.chooseIconAction)
      self.addAction(self.renameAction)
      self.addAction(self.propertiesAction)
      self.addSeparator()
      self.addAction(self.removeAction)
      
      self.InitConnections()
      
   def InitConnections(self):
      if self.parent() is not None:
         self.chooseIconAction.triggered.connect(self.parent().ChooseIconForItem)
         self.propertiesAction.triggered.connect(self.parent().EditItem)
         self.renameAction.triggered.connect(self.parent().RenameItem)
         self.removeAction.triggered.connect(self.parent().RemoveItem)

#class CategoryTWidget(QtGui.QTableWidget):
#   ProfileChanged = pyqtSignal()
#   
#   def __init__(self, iconSize = 48):
#      QtGui.QTableWidget.__init__(self, 6, 6)
#      
#      # layout/design initialization 
#      self.iconSize = iconSize
#      self.contextMenu = EntryMenu(self)
#      self.count = 0
#      
#      self.setVerticalHeaderItem(1, QtGui.QTableWidgetItem(""))
#      
#      self.clearSelection()
#      
#      style  = "QTableView { background-image: url(wood-texture.jpg); color: white; background-attachment: fixed; }"\
#             + "QTableView::item { border: 1px solid rgba(0,0,0,0%); }"\
#             + "QTableView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
#             + "QTableView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
#      self.setStyleSheet(style)
#      
#      # connections
#      self.itemDoubleClicked.connect(self.RunItem)
#
#   def contextMenuEvent(self, e):
#      lwitem = self.itemAt(e.pos())
#      if lwitem is not None:
#         self.contextMenu.exec_(e.globalPos())
#         
#   def dropEvent(self, e):
#      QtGui.QListView.dropEvent(self, e)
#      
#      item = self.itemAt(e.pos())
#      if item is not None:
#         #newpos = (r.top()/self.gridSize().height(), r.left()/self.gridSize().width())
#         newpos = ( item.row(), item.col() )
#         if newpos != item.entry.position:
#            item.entry.position = newpos
#            self.ProfileChanged.emit()
#         
#   def mousePressEvent(self, e):
#      if self.itemAt(e.pos()) is None:
#         self.clearSelection()
#         
#      QtGui.QAbstractItemView.mousePressEvent(self, e)
#
#   def AddEntry(self, entry):
#      e = EntryListTItem(entry=entry, parent=self, iconSize=self.iconSize)
#      
#      pos = self.count//self.columnCount(), self.count%self.columnCount()
#      self.setItem(pos[0], pos[1], e)
#      e.entry.position = pos
#      
#      self.count += 1
#      
#   def ChooseIconForItem(self):
#      item = self.currentItem()
#      if not item: return
#      dlg = ChooseIconDialog(self, file=item.entry.filename, suggestions=True)
#      result = dlg.exec_()
#      
#      if result == None: return
#      else:
#         path, id = result
#         item.entry.iconPath = path
#         item.entry.preferredIcon = id
#         item.entry.LoadIcon()
#         item.UpdateIcon()
#         item.entry.UpdateProfile.emit()
#         
#   def RemoveItem(self):
#      item = self.currentItem()
#      if not item: return
#      
#      self.parent().RemoveItemT(item.entry, item.row(), item.column())
#
#   def RenameItem(self):
#      item = self.currentItem()
#      if not item: return
#      entry = item.entry
#      
#      text, accepted = QtGui.QInputDialog.getText(self, "Rename %s" % entry.label, "Please enter new name:", text=entry.label)
#      if accepted:
#         entry.label = text
#         item.UpdateText()
#         item.entry.UpdateProfile.emit()
#         
#   def RunItem(self,item):
#      item.entry.Run()
      

class CategoryWidget(QtGui.QListWidget):
   ProfileChanged = pyqtSignal()
   IconChanged = pyqtSignal()
   
   def __init__(self, parent=None, iconSize = 48):
      QtGui.QListWidget.__init__(self, parent)
      
      self.iconSize = iconSize
      self.contextMenu = EntryMenu(self)
      
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
      """ Abstract method, please reimplement in subclasses to add entries to the list. """
      raise NotImplementedError('Call to abstract class method \'AddEntry\' in EntryItem-object.')
      
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
         self.IconChanged.emit()
         item.entry.UpdateProfile.emit()
         
   def EditItem(self):
      item = self.currentItem()
      if not item: return
      dlg = EntryPropertiesDialog(entry=item.entry, parent=self)
      result = dlg.exec_()
         
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
      
class CategoryListWidget(CategoryWidget):
   def __init__(self, parent=None, iconSize = 16):
      CategoryWidget.__init__(self, parent, iconSize)
      
      # layout/design initialization
      self.setViewMode(QtGui.QListView.ListMode)
      
      size = QtCore.QSize(iconSize,iconSize)
      
      self.setIconSize(size)
      self.setMovement(QtGui.QListView.Static)
      
      style  = "QListView { background-image: url(wood-texture.jpg); color: white; background-attachment: fixed; }"\
             + "QListView::item { border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
      #self.setStyleSheet(style)
      
   def AddEntry(self, entry):
      e = EntryListItem(entry=entry, parent=self, iconSize=self.iconSize)

class CategoryIconWidget(CategoryWidget):
   def __init__(self, parent=None, iconSize = 128):
      CategoryWidget.__init__(self, parent, iconSize)
            
      # layout/design initialization 
      size = QtCore.QSize(iconSize,iconSize)
      textSize = QtCore.QSize(0, 33)
      spacing = QtCore.QSize(20,20)
      
      self.setViewMode(QtGui.QListView.IconMode)
      self.setSpacing(20)
      self.setIconSize(size)
      self.setGridSize(size+textSize+spacing)
      self.setMovement(QtGui.QListView.Static)
      #self.setResizeMode(QtGui.QListView.Adjust)
      
      self.setUniformItemSizes(True)
      
      self.clearSelection()
      
      style  = "QListView { background-image: url(wood-texture.jpg); background-attachment: fixed; }"\
             + "QListView::item { color: white; border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
             + "QListView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
      self.setStyleSheet(style)
      
   def AddEntry(self, entry):
      e = EntryIconItem(entry=entry, parent=self, iconSize=self.iconSize)

class DetailsWidget(QtGui.QWidget):
   """ Shows detailed information on an entry, such as a large icon, its title and playtime """
   def __init__(self, parent=None, entry=None):
      QtGui.QWidget.__init__(self, parent)
      self.entry = entry
      
      # init labels
      nameFont = QtGui.QFont("Calibri", 20, QtGui.QFont.Bold)
      self.nameLabel = QtGui.QLabel("Unknown application")
      self.nameLabel.setFont(nameFont)
      
      timeFont = QtGui.QFont("Calibri", 12, italic=True)
      self.playtimeLabel = QtGui.QLabel("Never played")
      self.playtimeLabel.setFont(timeFont)
      picture = QtGui.QPixmap("noicon.png")
      self.pictureLabel = QtGui.QLabel()
      self.pictureLabel.setPixmap(picture)
   
      if self.entry is not None: self.SetEntry(entry)
   
      # init layout
      lay = QtGui.QHBoxLayout()
      
      layV = QtGui.QVBoxLayout()
      
      layV.addStretch(1)
      layV.addWidget(self.nameLabel, 0, QtCore.Qt.AlignVCenter)
      layV.addWidget(self.playtimeLabel, 0, QtCore.Qt.AlignVCenter)
      layV.addStretch(1)
      
      lay.addWidget(self.pictureLabel)
      lay.addLayout(layV)
      
      self.setLayout(lay)
      
   def SetEntry(self, entry):
      self.entry = entry
      self.nameLabel.setText(entry.label)
      picture = entry.icon.pixmap(256,256)
      self.pictureLabel.setPixmap(picture)
      self.UpdateText()
      
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
      self.playtimeLabel.setText(timeText)
      
class CategoryListAndDetailsWidget(QtGui.QWidget):
   ProfileChanged = pyqtSignal()
   
   def __init__(self, parent=None):
      QtGui.QWidget.__init__(self, parent)
      
      # init layout
      lay = QtGui.QHBoxLayout()
      
      self.catWdg = CategoryListWidget(self)
      self.detWdg = DetailsWidget(self)
      
      lay.addWidget(self.catWdg)
      lay.addWidget(self.detWdg, 1, QtCore.Qt.AlignTop ) # higher stretch
      
      self.setLayout(lay)
      
      # connect widgets
      self.catWdg.ProfileChanged.connect(self.ProfileChangedSlot)
      self.catWdg.currentItemChanged.connect(self.CurrentItemChanged)
      self.catWdg.IconChanged.connect(self.IconChanged)
      
      # set stylesheet
      style  = " background-image: url(wood-texture.jpg); color: white; background-attachment: fixed; "\
             + "QLabel { color: white; }"\
             + "QListView { color: white; }"\
      #       + "QListView::item { border: 1px solid rgba(0,0,0,0%); }"\
      #       + "QListView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
      #       + "QListView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
      #self.setStyleSheet(style)
   
   def count(self):
      return self.catWdg.count()
   
   def currentRow(self):
      return self.catWdg.currentRow()
   
   def insertItem(self, row, item):
      return self.catWdg.insertItem(row, item)
   
   def item(self, row):
      return self.catWdg.item(row)
   
   def row(self, item):
      return self.catWdg.row(item)
   
   def setCurrentRow(self, row):
      return self.catWdg.setCurrentRow(row)
   
   def takeItem(self, row):
      return self.catWdg.takeItem(row)
      
   def AddEntry(self, entry):
      self.catWdg.AddEntry(entry)
      
   def CurrentItemChanged(self, item):
      self.detWdg.SetEntry(item.entry)
      
   def IconChanged(self):
      item = self.catWdg.currentItem()
      self.CurrentItemChanged(item)
      
   def ProfileChangedSlot(self):
      # just pass this signal on
      self.ProfileChanged.emit()
      
   def RemoveItem(self, item, row):
      self.parent().RemoveItem(item, row)
      
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
         if iconSize == 16: wdg = CategoryListAndDetailsWidget(self)
         else: wdg = CategoryIconWidget(self, iconSize)
         self.catWidgets[iconSize] = wdg
         self.catWidgetIndices[iconSize] = self.layout().addWidget(wdg)
         wdg.ProfileChanged.connect(self.parent().SaveProfile)
         
      self.SetIconSize(self.iconSize)
      
   def MoveItemUp(self):
      row = self.activeCatWdg.currentRow()
      if row == 0: return
      self.SwapItems(row, row-1)
      self.activeCatWdg.setCurrentRow(row-1)
      
   def MoveItemDown(self):
      row = self.activeCatWdg.currentRow()
      if row == self.activeCatWdg.count()-1: return
      self.SwapItems(row, row+1)
      self.activeCatWdg.setCurrentRow(row+1)
      
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
         entry.LoadIcon(256) # always load largest icon because otherwise we would scale up when increasing icon size at runtime
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
      
   def RemoveItemT(self, entry, row, col):
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
         i = wdg.takeItem(row,col)
         del i
      
      self.parent().SaveProfile()
         
   def SetIconSize(self, size):
      self.iconSize = size
      self.layout().setCurrentIndex(self.catWidgetIndices[size])
      self.activeCatWdg = self.catWidgets[size]
      
   def SwapItems(self, id_a, id_b):
      e_a = self.entries[id_a]
      e_b = self.entries[id_b]
      
      self.entries[id_a] = e_b
      self.entries[id_b] = e_a
      
      for wdg in self.catWidgets.values():
         itm_a = wdg.item(id_a)
         itm_b = wdg.item(id_b)
         
         wdg.takeItem(wdg.row(itm_a))
         wdg.takeItem(wdg.row(itm_b))
         
         if id_a < id_b:
            wdg.insertItem(id_a, itm_b)
            wdg.insertItem(id_b, itm_a)
         else:
            wdg.insertItem(id_b, itm_a)
            wdg.insertItem(id_a, itm_b)
      
class ToolsToolbar(QtGui.QToolBar):
   def __init__(self, parent=None):
      QtGui.QToolBar.__init__(self, "Tools", parent)
      
      # init children
      self.iconSizeComboBox = IconSizeComboBox()
      self.upBtn = QtGui.QPushButton()
      self.upBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-up-icon.png")))
      
      self.downBtn = QtGui.QPushButton()
      self.downBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-down-icon.png")))
      
      # init layout
      dwWdg = QtGui.QWidget(self)
      dwWdg.setLayout(QtGui.QHBoxLayout())
      
      dwWdg.layout().addStretch(1)
      dwWdg.layout().addWidget(self.upBtn)
      dwWdg.layout().addWidget(self.downBtn)
      dwWdg.layout().addWidget(self.iconSizeComboBox)
      
      self.addWidget(dwWdg)

class MainWindow(QtGui.QMainWindow):
   def __init__(self):
      QtGui.QMainWindow.__init__(self)
      
      # UI initialization
      self.resize(800,600)
      self.setWindowTitle("FireStarter")
      self.setWindowIcon(QtGui.QIcon("fire.ico"))
      
      self.setCentralWidget(MainWidget(self))
      
      # init toolbar
      self.toolsBar = ToolsToolbar(self)
      self.addToolBar(self.toolsBar)
      
      # init menus and connections
      self.InitMenus()
      self.InitConnections()
      
      # init profile      
      self.profile = os.environ.get("USERNAME")
      self.LoadProfile()
      
   def __del__(self):
      print "Saving profile prior to closing program..."
      self.SaveProfile()
      
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
      self.toolsBar.iconSizeComboBox.IconSizeChanged.connect(self.SetIconSize)
      self.toolsBar.upBtn.clicked.connect(self.centralWidget().MoveItemUp)
      self.toolsBar.downBtn.clicked.connect(self.centralWidget().MoveItemDown)
   
   def InitMenus(self):
      self.settingsMenu = SettingsMenu(self, self.centralWidget().iconSize)
      self.viewMenu = ViewMenu(self, showTools=self.toolsBar.toggleViewAction())
      
      self.menuBar().addMenu(self.viewMenu)
      self.menuBar().addMenu(self.settingsMenu)
      
   def LoadProfile(self, filename=None):
      if filename is None: filename = '%s.dat' % self.profile
      if not os.path.exists(filename): return
      
      shutil.copyfile(filename, "~"+filename+".bak")
      error = False
      
      with open(filename, 'r') as f:
         try:
            iconSize = pickle.load(f)
            numEntries = pickle.load(f)
            
            # restore window size and position
            size = pickle.load(f)
            self.resize(size[0], size[1])
            pos = pickle.load(f)
            self.move(pos[0],pos[1])
            
            toolsVisible = pickle.load(f)
            self.toolsBar.setVisible(toolsVisible)
         except:
            QtGui.QMessageBox.critical(self, "Error", "Invalid profile '%s'!" % filename)
            return
         
         # set correct icon size
         try:
            self.SetIconSize(iconSize)
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
         pickle.dump( self.viewMenu.showTools.isChecked(), f)  # write if tools toolbar is visible; must check showTools action
                                                               #because the toolbar itself was already destroyed and is not visible anymore
         for entry in self.centralWidget().entries:
            entry.ExportToFile(f)
         
         #print "Saved profile in %f seconds." % (time.clock() - startTime)
         
   def SetIconSize(self, size):
      self.iconSize = size
      self.toolsBar.iconSizeComboBox.SetCurrentSize(size)
      self.settingsMenu.CheckIconSizeAction(size)

      self.centralWidget().SetIconSize(size)
      
      self.SaveProfile()

   def UpdateIconSizeFromMenu(self):
      # determine new icon size
      curAction = self.settingsMenu.iconSizeActions.checkedAction().text()
      size = int(curAction.split('x')[0])
      self.SetIconSize(size)


class ViewMenu(QtGui.QMenu):
   def __init__(self, parent=None, showTools=None):
      QtGui.QMenu.__init__(self, "&View", parent)
      
      if showTools:
         self.showTools = showTools
         self.showTools.setText("Show &tools")
         self.addAction(self.showTools)
      
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
