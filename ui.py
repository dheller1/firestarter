# -*- coding: utf-8 -*-
'''
Created on 03.01.2013

@author: heller
'''

#import os, time
import ctypes
#import pickle
#import subprocess, threading
import shutil
import codecs
import sqlite3

#from ctypes import byref
from types import *

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

from widgets import ToolsToolbar #IconSizeComboBox
from entries import *
from dialogs import *
from util import din5007, EntrySettings, SteamEntrySettings, ProfileSettings, EntryHistory, FileParser, formatTime, formatLastPlayed, openFileWithCodepage, stringToFilename
from steamapi import SteamGameStats

class EntryWidget(QtGui.QWidget):
   # base class for new-style entry items which are custom widgets instead of ListWidgetItems
   # and live within a custom widget instead of a certain type of ListWidget
   def __init__(self, entry=None, parent=None, iconSize=48):
      QtGui.QWidget.__init__(self, parent)
      self.InitLayout()
      
      self.iconSize = iconSize
      self.parent = parent
      self.showPlaytime = True
      
      if not entry: return
      if entry.icon is not None: self.icon = entry.icon
      self.entry = entry
      self.UpdateText()
      
      self.entry.UpdateText.connect(self.UpdateText)
      self.entry.UpdateIcon.connect(self.UpdateIcon)
      
   def parent(self):
      return self.parent if self.parent else None
   
   def InitLayout(self):
      lay = QtGui.QVBoxLayout()
      
      self.icon = QtGui.QIcon()
      self.nameLbl = QtGui.QLabel("Unnamed entry")
      
      lay.addWidget(self.icon)
      lay.addWidget(self.nameLbl)
      
      self.setLayout(lay)
      
   def UpdateIcon(self):
      self.icon = self.entry.icon
      
   def UpdateText(self):
      entry = self.entry
      if entry.running: timeText = "Currently running... %s" % formatTime(entry.currentSessionTime)
      else:
         if entry.totalTime == 0.: timeText ="Never played"
         else: 
            timeText = formatTime(entry.totalTime) + " played"
            
            # not enough space for this! only showed in list/details mode (16x16px) currently
            #timeText += ", last played: " + formatLastPlayed(entry.lastPlayed)
      
      if self.showPlaytime:
         text = entry.label + "\n" + timeText
      elif entry.running:
         text = entry.label + " - Currently running..."
      else: text = entry.label
      
      self.nameLbl.setText(text)
      
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
      if entry.running: timeText = "Currently running... %s" % formatTime(entry.currentSessionTime)
      else:
         if entry.totalTime == 0.: timeText ="Never played"
         else: 
            timeText = formatTime(entry.totalTime) + " played"
            
            # not enough space for this! only showed in list/details mode (16x16px) currently
            #timeText += ", last played: " + formatLastPlayed(entry.lastPlayed)
      
      if self.showPlaytime:
         text = entry.label + "\n" + timeText
      elif entry.running:
         text = entry.label + " - Currently running..."
      else: text = entry.label
      
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

class CategoryWidget(QtGui.QListWidget):
   FirstItemSelected = pyqtSignal()
   IconChanged = pyqtSignal()
   LastItemSelected = pyqtSignal()
   EnableReorderButtons = pyqtSignal()
   ProfileChanged = pyqtSignal()
   
   def __init__(self, parent=None, iconSize = 48):
      QtGui.QListWidget.__init__(self, parent)
      
      self.iconSize = iconSize
      self.contextMenu = EntryMenu(self)
      
      # connections
      self.itemActivated.connect(self.RunItem)
      self.itemSelectionChanged.connect(self.ItemSelectionChanged)
      self.currentRowChanged.connect(self.ItemSelectionChanged) # connect this too, as reordering might change row but keep item selection

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
         item.entry.UpdateIcon.emit()
         self.IconChanged.emit()
         item.entry.UpdateProfile.emit()
         
   def EditItem(self):
      item = self.currentItem()
      if not item: return
      dlg = EntryPropertiesDialog(entry=item.entry, parent=self)
      result = dlg.exec_()
      
   def ItemSelectionChanged(self):
      row = self.currentRow()
      
      if len(self.selectedItems())==0:
         # nothing selected, disable both directions
         self.FirstItemSelected.emit() # disables 'Up'
         self.LastItemSelected.emit()  # disables 'Down'
         return
      
      self.EnableReorderButtons.emit() # enables both directions
      if row == 0:
         self.FirstItemSelected.emit() # disables 'Up'
      if row == self.count()-1:
         self.LastItemSelected.emit()  # disables 'Down'
         
   def RemoveItem(self):
      item = self.currentItem()
      if not item: return
      
      self.parent().RemoveItem(item)
      
   def RenameItem(self):
      item = self.currentItem()
      if not item: return
      entry = item.entry
      
      text, accepted = QtGui.QInputDialog.getText(self, "Rename %s" % entry.label, "Please enter new name:", text=entry.label)
      if accepted:
         entry.label = unicode(text)
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
      
      style  = "QListView { background-image: url(gfx/wood-texture.jpg); color: white; background-attachment: fixed; }"\
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
      
      style  = "QListView { background-image: url(gfx/wood-texture.jpg); background-attachment: fixed; }"\
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
      picture = QtGui.QPixmap(os.path.join("gfx","noicon.png"))
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
         else: 
            timeText = formatTime(entry.totalTime) + " played"
            timeText += "\nLast played: " + formatLastPlayed(entry.lastPlayed)
      
      self.playtimeLabel.setText(timeText)
      
class CategoryListAndDetailsWidget(QtGui.QWidget):
   FirstItemSelected = pyqtSignal()
   IconChanged = pyqtSignal()
   LastItemSelected = pyqtSignal()
   EnableReorderButtons = pyqtSignal()
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
      
      self.catWdg.FirstItemSelected.connect(self.FirstItemSelectedSlot)
      self.catWdg.LastItemSelected.connect(self.LastItemSelectedSlot)
      self.catWdg.EnableReorderButtons.connect(self.EnableReorderButtonsSlot)
      
      # set stylesheet
      style  = " background-image: url(gfx/wood-texture.jpg); color: white; background-attachment: fixed; "\
             + "QLabel { color: white; }"\
             + "QListView { color: white; }"\
      #       + "QListView::item { border: 1px solid rgba(0,0,0,0%); }"\
      #       + "QListView::item:hover { background: rgba(0,0,0, 18%); border: 1px solid rgba(0,0,0,0%); }"\
      #       + "QListView::item:selected { background: rgba(0,0,0, 35%); border: 1px solid black; }"
      #self.setStyleSheet(style)
   
   def clear(self):
      return self.catWdg.clear()
   
   def clearSelection(self):
      return self.catWdg.clearSelection()
   
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
   
   def selectedItems(self):
      return self.catWdg.selectedItems()
   
   def setCurrentRow(self, row):
      return self.catWdg.setCurrentRow(row)
      
   def sortItems(self):
      self.catWdg.sortItems()
         
   def takeItem(self, row):
      return self.catWdg.takeItem(row)
      
   def AddEntry(self, entry):
      self.catWdg.AddEntry(entry)
      
   def CurrentItemChanged(self, item):
      if item is not None:
         self.detWdg.SetEntry(item.entry)
      
   def IconChanged(self):
      item = self.catWdg.currentItem()
      self.CurrentItemChanged(item)
      
   def RemoveItem(self, item, row):
      self.parent().RemoveItem(item, row)
   
   # just pass these signals on
   def EnableReorderButtonsSlot(self):
      self.EnableReorderButtons.emit()
   def FirstItemSelectedSlot(self):
      self.FirstItemSelected.emit()
   def LastItemSelectedSlot(self):
      self.LastItemSelected.emit()
   def ProfileChangedSlot(self):
      self.ProfileChanged.emit()
   
      
class MainWidget(QtGui.QWidget):
   ManualSortingEnabled = pyqtSignal()
   PlaytimeChanged = pyqtSignal(int)
   
   def __init__(self, parent=None):
      QtGui.QWidget.__init__(self, parent)
      
      self.setAcceptDrops(True)
      self.entries = []
      self.lastManuallySortedEntries = self.entries
      self.InitLayout()
      
      self.isManuallySorted = True
      self.sortMode = "manual"
      
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
      
   def AddEntry(self, entry, manuallySorted = False):
      self.entries.append(entry)
      
      # send to child layouts
      for catWdg in self.catWidgets.values():
         catWdg.AddEntry(entry)
         
      entry.UpdateProfile.connect(self.parent().SaveProfile)
      entry.UpdateProfile.connect(self.UpdatePlaytime)
      entry.ManualTracking.connect(self.StartManualTracking)
      
      if manuallySorted:
         self.lastManuallySortedEntries = self.entries
         self.isManuallySorted = True
         
      self.UpdatePlaytime()
      
   def AddManuallyTrackedTime(self, entry, time):
      if not entry.running:
         entry.totalTime += time
         #print "Added %s to %s." % (formatTime(time), entry.label)
      else:
         raise Exception("FATAL: Trying to add manual time to a running entry!")
      
      entry.UpdateText.emit()
      entry.UpdateProfile.emit()
      
   def ConnectToToolsBar(self, tb):
      for wdg in self.catWidgets.values():
         wdg.EnableReorderButtons.connect(tb.EnableButtons)
         wdg.FirstItemSelected.connect(tb.DisableUpButton)
         wdg.LastItemSelected.connect(tb.DisableDownButton)
         
      self.PlaytimeChanged.connect(tb.UpdatePlaytime)
      
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
      
      self.SetNewManualOrder()
      
   def MoveItemDown(self):
      row = self.activeCatWdg.currentRow()
      if row == self.activeCatWdg.count()-1: return
      self.SwapItems(row, row+1)
      self.activeCatWdg.setCurrentRow(row+1)
      
      self.SetNewManualOrder()
      
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
         entry.LoadIcon(256) # load default icon
         
      if entry.preferredIcon != -1:
         # try to copy and save icon to a local folder in case the icon becomes unavailable in the future
         pm = entry.icon.pixmap(entry.icon.actualSize(QtCore.QSize(256,256)))
         
         iconFilename = stringToFilename(entry.label)
         i = 0
         while(os.path.exists(os.path.join("cache", "icons", iconFilename))):
            iconFilename = "%s%i" % (stringToFilename(entry.label), i)
            
         fullName = os.path.join("cache", "icons", iconFilename+".png")
         pm.save(fullName, "PNG", 100)
         entry.preferredIcon = -2
         entry.iconPath = fullName
      
      self.AddEntry(entry)
      self.parent().SaveProfile()
      self.SetNewManualOrder()
   
   def Refill(self, entries):
      """ Clear all entries and repopulate the list with the given entries, which might be a sorted version of the old list,
        for instance. """
      self.entries = []
      
      for catWdg in self.catWidgets.values():
         catWdg.clear()
         
      for e in entries:
         self.AddEntry(e)
      
   def RemoveItem(self, item):
      msg = QtGui.QMessageBox(QtGui.QMessageBox.Warning, "Warning: Deleting entry", "Do you really want to remove this entry? All"+\
                              " information and playtime will be lost and can not be restored!", QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel, self)
      result = msg.exec_()
      if result == QtGui.QMessageBox.Cancel: return
      
      # find entry
      try:
         index = self.entries.index(item.entry)
      except ValueError:
         raise ValueError("Tried to remove entry from main widget's entry list, but it is not present!")
      
      # delete entry
      self.entries.pop(index)
      self.lastManuallySortedEntries.pop(self.lastManuallySortedEntries.index(item.entry))
      
      row = self.layout().currentWidget().row(item)
      for wdg in self.catWidgets.values():
         i = wdg.takeItem(row)
         del i
      
      self.parent().SaveProfile()
      
   def RestoreLastManualSorting(self):
      if self.isManuallySorted: return
      else:
         self.sortMode = "manual"
         self.isManuallySorted = True
         self.Refill(self.lastManuallySortedEntries)
         
   def SetIconSize(self, size):
      self.iconSize = size
      
      if len(self.layout().currentWidget().selectedItems()) > 0:
         curRow = self.layout().currentWidget().currentRow()
      else: curRow = -1
      self.layout().setCurrentIndex(self.catWidgetIndices[size])
      self.activeCatWdg = self.catWidgets[size]
      
      if curRow >= 0:
         self.layout().currentWidget().setCurrentRow(curRow)
      else: self.layout().currentWidget().clearSelection()
      
   def SetNewManualOrder(self):
      """ Set the current entry order as the new manual one. """
      self.sortMode = "manual"
      self.isManuallySorted = True
      self.lastManuallySortedEntries = self.entries
      
      self.ManualSortingEnabled.emit()

   def SortByCurrentSortMode(self):
      if self.sortMode == "time": self.SortByTime()
      elif self.sortMode == "title": self.SortByTitle()
      else: return # manual sorting or unsupported string
      
   def SortByTime(self):
      if self.isManuallySorted:
         self.lastManuallySortedEntries = self.entries
      
      self.isManuallySorted = False
      self.sortMode = "time"
      # sort all child widgets by time   
      entries = sorted(self.entries, key=lambda entry: entry.totalTime, reverse=True)
      self.Refill(entries)
      
   def SortByTitle(self):
      if self.isManuallySorted:
         self.lastManuallySortedEntries = self.entries
      
      self.isManuallySorted = False   
      self.sortMode = "title"
      # sort all child widgets by title
      entries = sorted(self.entries, key=lambda entry: din5007(entry.label))
      self.Refill(entries)
      
   def StartManualTracking(self, entry):
      dlg = ManualTrackingDialog(entry, self)
      dlg.show()
      dlg.AddTimeSignal.connect(self.AddManuallyTrackedTime)
      
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
            
   def UpdatePlaytime(self):
      self.PlaytimeChanged.emit(sum([e.totalTime for e in self.entries]))
      
class MainWindow(QtGui.QMainWindow):
   RestartCode = 1337
   
   def __init__(self):
      QtGui.QMainWindow.__init__(self)
      
      # UI initialization
      self.resize(800,600)
      self.setWindowTitle("FireStarter")
      self.setWindowIcon(QtGui.QIcon(os.path.join("gfx","fire.ico")))
      
      self.setCentralWidget(MainWidget(self))
      
      # init toolbar
      self.toolsBar = ToolsToolbar(self)
      self.addToolBar(self.toolsBar)
      self.centralWidget().ConnectToToolsBar(self.toolsBar)

      # init menus and connections
      self.InitMenus()
      self.InitConnections()
      
      # init profile      
      self.fileParser = FileParser()
      self.erroneousProfile = False
      self.profile = ProfileSettings()
      
      self.autosaveDisabled = False
      
      lastProfile = self.GetLastProfileName() # try to determine last profile first
      if lastProfile is not None and not os.path.isfile(lastProfile):
         QtGui.QMessageBox.warning(self, "Warning", "Could not find your last profile '%s'.\nPlease select a profile manually." % lastProfile)
         lastProfile = None
         
      if lastProfile is None: # if failed, let the user select a profile or create a new one
         selectedProfile = self.InvokeProfileSelection()
            
      if lastProfile is not None: self.profileName = lastProfile
      elif selectedProfile is not None: self.profileName = selectedProfile
      else:
         self.profileName = None
         self.erroneousProfile = True
         QtGui.QMessageBox.information(self, "Information", "No profile was selected.\nChanges made during this session will not be saved.")
         
      if self.profileName is not None:
         try:
            self.LoadProfile(self.profileName)
         except (ValueError, EOFError, IOError) as e:
            self.erroneousProfile = True # this will disable saving the profile completely.
            QtGui.QMessageBox.critical(self, "Error", ("An error occured when loading the profile '%s'.\n" % self.profileName) + \
                                       "Please fix your profile and restart the program.\nChanges made during this session will not be saved." + \
                                       "\n\nError message: '%s'" % str(e))
   
   # reimplemented Qt-style in closeEvent  
   #def __del__(self):
   #   self.SaveProfile()
   #   self.fileParser.__del__()
   
   def closeEvent(self, e):
      self.hide()
      
      if not self.autosaveDisabled:
         self.SaveProfile()
         
      self.fileParser.__del__()
      QtGui.QMainWindow.closeEvent(self, e)
   
   #def moveEvent(self, e):
   #   pass
      
   #def resizeEvent(self, e):
   #   pass
   
   def ConnectToSteamProfile(self):
      # if another connect to steam dialog was canceled and then this routine is called shortly afterwards,
      # the old query thread might still be active, delaying deletion of the old dialog object and leading
      # to an error when QT cleanup routines want the worker thread to disconnect timers set by the main thread.
      # Thus, wait until the old query has finished.
      # This should happen very rarely though.
      if hasattr(self, 'steamConnectDlg'):
         if self.steamConnectDlg.queryThread.isAlive():
            self.steamConnectDlg.queryThread.join()
         
      dlg = self.steamConnectDlg = SteamProfileDialog(self)
      result = dlg.exec_()
      if result == QtGui.QDialog.Accepted:
         if self.profile.steamId not in ('0', None):
            confirm = QtGui.QMessageBox.question(self, "Please confirm", "This profile is already connected to a Steam account with id"\
                                                 +" <b>%s</b>.\n" % self.profile.steamId\
                                                 + "Do you want to replace the connection with the new account <b>%s</b>?" %dlg.steamId,\
                                                 QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            if confirm == QtGui.QMessageBox.No: return
         self.profile.steamId = dlg.steamId
         
         if dlg.downloadProfileData:
            self.setCursor(Qt.WaitCursor)
            QtGui.qApp.processEvents()
            
            api = SteamApi()
            games = api.GetOwnedGames(dlg.steamId)
            
            gameObjs = []
            for g in games:
               if "playtime_forever" in g and g["playtime_forever"] > 0:
                  gameObj = SteamGameStats(g["appid"], g["name"], g["playtime_forever"], g["img_icon_url"], g["img_logo_url"])
                  gameObjs.append(gameObj)
                   
            dls = 0
            alreadyPresent = 0
            
            # download icons
            for g in gameObjs:
               iconurl = "http://media.steampowered.com/steamcommunity/public/images/apps/%s/%s.jpg" % (g.appid, g.iconUrl)
               localPath = os.path.join("cache", "steam", "%s_%s.jpg" % (g.appid, g.iconUrl)) 
               
               if os.path.isfile(localPath):
                  alreadyPresent += 1
                  continue
               
               try:
                  with open(localPath, 'wb') as localFile:
                     iconFile = urllib2.urlopen(iconurl, timeout=20)
                     localFile.write(iconFile.read())
                     iconFile.close()
                  dls += 1
               except (IOError, urllib2.URLError):
                  continue

               #print "%s: %s" % (g.name, formatTime(60.*g.playtime))
            
            self.profile.steamGames = []
            for sgs in gameObjs:
               se = SteamEntry()
               se.ImportFromSteamGameStats(sgs)
               self.profile.steamGames.append(se)
               
            self.setCursor(Qt.ArrowCursor)
         
         self.SaveProfile()
   
   def GetLastProfileName(self):
      if not os.path.isfile('lastprofile'): return None
      
      with openFileWithCodepage('lastprofile', 'r') as f:
         lastprofile = f.readline()

      return lastprofile if len(lastprofile) > 0 else None
 
   def InitConnections(self):
      self.toolsBar.iconSizeComboBox.IconSizeChanged.connect(self.SetIconSize)
      self.toolsBar.upBtn.clicked.connect(self.centralWidget().MoveItemUp)
      self.toolsBar.downBtn.clicked.connect(self.centralWidget().MoveItemDown)
      self.toolsBar.statsBtn.clicked.connect(self.ShowStats)
      
      self.toolsBar.sortComboBox.ManualSortingSelected.connect(self.centralWidget().RestoreLastManualSorting)
      self.toolsBar.sortComboBox.SortByTitleSelected.connect(self.centralWidget().SortByTitle)
      self.toolsBar.sortComboBox.SortByTimeSelected.connect(self.centralWidget().SortByTime)
      
      self.centralWidget().ManualSortingEnabled.connect(self.toolsBar.sortComboBox.SelectManualSorting)
   
   def InitMenus(self):
      self.settingsMenu = SettingsMenu(self, self.centralWidget().iconSize)
      self.viewMenu = ViewMenu(self, showTools=self.toolsBar.toggleViewAction())
      self.fileMenu = FileMenu(self)
      self.profileMenu = ProfileMenu(self)
      
      self.menuBar().addMenu(self.fileMenu)
      self.menuBar().addMenu(self.profileMenu)
      self.menuBar().addMenu(self.viewMenu)
      self.menuBar().addMenu(self.settingsMenu)
      
   def InvokeProfileSelection(self):
      pDlg = ProfileSelectionDialog(self)
      result = pDlg.exec_()
      if result == QtGui.QDialog.Rejected:
         return None
            
      elif result == QtGui.QDialog.Accepted:
         if pDlg.newProfile:
            self.SaveDefaultProfile(pDlg.profileName)
         return pDlg.profileName
      
   def ManageLibrary(self):
      entries = []
      entries.extend(self.centralWidget().entries)
      entries.extend(self.profile.steamGames)
      
      dlg = ManageLibraryDialog(entries)
      dlg.exec_()
   
   def LoadProfile(self, filename=None, loadFromDb=True):
      """ Load profile specified by filename, or by self.profileName if no filename is given.
        Returns True if loading was erroneous, otherwise returns False. """
      bestProfileVersion = '0.1c'
      bestEntryVersion   = '0.1b'
      bestSteamEntryVersion='Steam_0.1a'
      
      backupProfile = False
      defaultBackup = True # always make a default backup as safety for loading errors
      
      updateInfoBoxAlreadyShowed = False
      
      if filename is None: filename = self.profileName
      if not os.path.exists(filename):
         # suppress this box as this error will just evoke the profile selection dialog
         #QtGui.QMessageBox.critical(self, "Error", "Profile '%s' not found!" % filename)
         raise IOError('Profile not found')
         return True
      
      if defaultBackup:
         shutil.copyfile(filename, "~"+filename+".bak")
      
      # determine encoding
      with open(filename, 'r') as f:
         codepage = f.readline().strip()
         codepage = codepage.replace('# -*- coding:','').replace('-*-','').strip()
         if len(codepage) == 0:
            raise ValueError('Empty profile')
            return True
      
      # try to open file with this encoding
      try:
         f = codecs.open(filename, 'r', codepage)
         f.close()
      except LookupError: # unknown coding
         QtGui.QMessageBox.critical(self, "Error", "Unknown codepage '%s' used in profile '%s'.\nPlease fix this manually. Loading empty profile." % (codepage, filename))
         raise ValueError('Unknown codepage')
         return True
      
      p = ProfileSettings()
      fp = self.fileParser
      
      # open file
      with codecs.open(filename, 'r', codepage) as f:
         f.readline() # skip codepage
         
         profileVersion = f.readline().strip() # read file format version
         if profileVersion not in FileParser.profileFormats:
            QtGui.QMessageBox.critical(self, "Profile error", "Unsupported file format (%s) for profile '%s'!\nAborting load process." % (profileVersion, filename))
            raise ValueError('Unsupported file format')
            return True
         try: fp.ParseByVersion(file=f, handler=p, version=profileVersion, type='profile')
         except ValueError as e:
            QtGui.QMessageBox.critical(self, "Profile loading error", str(e))
            raise ValueError(str(e))
            return True
         
         if bestProfileVersion != profileVersion:
            count = fp.CompleteProfile(p, bestProfileVersion)
            backupProfile = True
            if count > 0 and not updateInfoBoxAlreadyShowed:
               QtGui.QMessageBox.information(self, "Information", "Your profile has been updated to a newer version.\n"\
                        + "Should any problems occur, a backup is available: %s" % (filename+"."+profileVersion))
               updateInfoBoxAlreadyShowed = True
         
         for i in range(p.numEntries):
            entryVersion = f.readline().strip() # read file format version
            
            if entryVersion.startswith('Steam'):
               entryType = 'steam'
               if entryVersion not in FileParser.steamEntryFormats:
                  QtGui.QMessageBox.critical(self, "Profile error", "Unsupported file format (%s) for Steam entry in profile '%s'!\nAborting load process." % (entryVersion, filename))
                  raise ValueError('Unsupported file format')
                  return True
               entry = SteamEntry()
               eHndlr = SteamEntrySettings()
            else:
               entryType  = 'entry'
               if entryVersion not in FileParser.entryFormats:
                  QtGui.QMessageBox.critical(self, "Profile error", "Unsupported file format (%s) for entry in profile '%s'!\nAborting load process." % (entryVersion, filename))
                  raise ValueError('Unsupported file format')
                  return True
               entry = AppStarterEntry(parentWidget=self.centralWidget())
               eHndlr = EntrySettings()
            
            try:
               fp.ParseByVersion(file=f, handler=eHndlr, version=entryVersion, type=entryType )
            except ValueError as e:
               QtGui.QMessageBox.critical(self, "Profile loading error (entry)", str(e))
               raise ValueError(str(e))
               return True
            except EOFError:
               QtGui.QMessageBox.critical(self, "End of file error", "Unable to load entry %i from profile '%s'!\nEntries might be incomplete." % (i+1, filename))
               raise EOFError('Incomplete entry')
               return True
            
            if type=='entry' and bestEntryVersion != entryVersion  \
              or type=='steam' and bestSteamEntryVersion != entryVersion:
               
               count = fp.CompleteEntry(eHndlr, bestEntryVersion if type=='entry' else bestSteamEntryVersion)
               backupProfile = True
               if count > 0 and not updateInfoBoxAlreadyShowed:
                  QtGui.QMessageBox.information(self, "Information", "Your profile has been updated to a newer version.\n"\
                        + "Should any problems occur, a backup is available: %s" % (filename+"."+profileVersion))
                  updateInfoBoxAlreadyShowed = True
                  
            # copy data from EntrySettings object to actual entry
            if entryType=='entry':
               for var, vartype in FileParser.entryFormats[bestEntryVersion]:
                  setattr(entry, var, getattr(eHndlr, var))
            elif entryType=='steam':
               for var, vartype in FileParser.steamEntryFormats[bestSteamEntryVersion]:
                  setattr(entry, var, getattr(eHndlr, var))
            
            failedToLoadIcon = False
            try: entry.LoadIcon(256) # always load largest icon because otherwise we would scale up when increasing icon size at runtime
            except IOError: # ignore icon loading errors, probably just opening the profile on another machine - just show the default icon
               failedToLoadIcon = True
               
            if entryType =='entry':
               # preferred icon only for non-steam entries
               if entry.preferredIcon != -1 and not failedToLoadIcon:
                  # try to copy and save icon to a local folder in case the icon becomes unavailable in the future
                  pm = entry.icon.pixmap(entry.icon.actualSize(QtCore.QSize(256,256)))
                  
                  iconFilename = stringToFilename(entry.label)
                  i = 0
                  while(os.path.exists(os.path.join("cache", "icons", iconFilename))):
                     iconFilename = "%s%i" % (stringToFilename(entry.label), i)
                     
                  fullName = os.path.join("cache", "icons", iconFilename+".png")
                  pm.save(fullName, "PNG", 100)
                  entry.preferredIcon = -2
                  entry.iconPath = fullName
               
               elif failedToLoadIcon:
                  entry.icon=QtGui.QIcon(os.path.join("gfx","noicon.png"))
               
               self.centralWidget().AddEntry(entry, manuallySorted=True) # always add as manually sorted, might be overwritten later
            
            elif entryType=='steam':
               p.steamGames.append(entry)
            
      if backupProfile:
         shutil.copy(filename, filename+"."+profileVersion)
            
      # apply settings      
      try: self.SetIconSize(p.iconSize)
      except ValueError: QtGui.QMessageBox.warning(self, "Warning", "Invalid icon size in profile: %ix%ipx" %(p.iconSize,p.iconSize))
      
      try: self.resize(p.windowSize[0], p.windowSize[1])
      except ValueError: QtGui.QMessageBox.warning(self, "Warning", "Invalid window size in profile: %ix%i" %(p.windowSize[0],p.windowSize[1]))
      
      try: self.move(p.windowPos[0], p.windowPos[1])
      except ValueError: QtGui.QMessageBox.warning(self, "Warning", "Invalid window position in profile: %i, %i" %(p.windowPos[0],p.windowPos[1]))
      
      if p.sortMode not in ("manual", "title", "time"):
         QtGui.QMessageBox.warning(self, "Warning", "Invalid sort mode '%s' in profile, defaulting to manual sorting." % p.sortMode)
         self.centralWidget().sortMode = "manual"
      else: self.centralWidget().sortMode = p.sortMode
      self.centralWidget().SortByCurrentSortMode()
      self.toolsBar.sortComboBox.setCurrentIndex(1 if p.sortMode == "title" else 2 if p.sortMode == "time" else 0)
      self.toolsBar.setVisible(p.toolsVisible)
      
      self.profile = p
      
      # store as last profile
      codepage = 'utf-8'
      with codecs.open('lastprofile', 'w', codepage) as f:
         f.write("# -*- coding: %s -*-\n" % codepage)
         f.write(filename)
         
      # update window title
      self.setWindowTitle(os.path.splitext(filename)[0] + " - FireStarter")
      
      return False
   
   def SaveDefaultProfile(self, filename):
      codepage = 'utf-8'
      profileVersion = '0.1c'
      
      p = ProfileSettings.Default()
      fp = self.fileParser
      
      with codecs.open(filename, 'w', codepage) as f:
         f.write("# -*- coding: %s -*-\n" % codepage)
         f.write(profileVersion+'\n')
         fp.WriteByVersion(file=f, handler=p, version=profileVersion, type='profile')
         # no entries
   
   def SaveProfile(self, filename=None, DisableAutosave=False, saveToDb=True):
      """ Save profile to filename or to the current profile name if no filename is specified.
        Use DisableAutosave to disable automatic saving (when closing the program) until the next
        manual save. """
      
      self.autosaveDisabled = DisableAutosave
      
      # do not save if profile was not loaded correctly
      if self.erroneousProfile: return
   
      if filename is None: filename = self.profileName
      
      codepage = 'utf-8'
      profileVersion = '0.1c'
      entryVersion   = '0.1b'
      steamEntryVersion='Steam_0.1a'
      
      p = self.profile
      
      # update profile to current settings before saving
      p.iconSize = self.centralWidget().iconSize
      p.numEntries = len(self.centralWidget().entries) + len(self.profile.steamGames)
      p.windowSize = (self.size().width(), self.size().height())
      p.windowPos = (self.x(), self.y())
      p.toolsVisible = self.viewMenu.showTools.isChecked()
      p.sortMode = self.centralWidget().sortMode
      
      if not saveToDb:
         fp = self.fileParser
         
         #startTime = time.clock()
         with codecs.open(filename, 'w', codepage) as f:
            f.write("# -*- coding: %s -*-\n" % codepage)
            
            f.write(profileVersion+'\n') # always write file format version first
            fp.WriteByVersion(file=f, handler=p, version=profileVersion, type='profile')
            
            for entry in self.centralWidget().lastManuallySortedEntries:
               f.write(entryVersion+'\n')# always write file format version first
               fp.WriteByVersion(file=f, handler=entry, version=entryVersion, type='entry')
               
            for se in self.profile.steamGames:
               f.write(steamEntryVersion+'\n')# always write file format version first
               fp.WriteByVersion(file=f, handler=se, version=steamEntryVersion, type='steam')
            #print "Saved profile in %f seconds." % (time.clock() - startTime)
      else:
         try: os.remove('test.sqlite')
         except: pass
         db = sqlite3.connect('test.sqlite')
         c = db.cursor()
         
         q = ProfileSettings.CreateTableQuery()
         try: c.execute(q)
         except sqlite3.OperationalError as e:
            print "Error in SQLite3 for Query:\n" + q
            print "Error message: '%s'" % e
         
         q = EntrySettings.CreateTableQuery()
         try: c.execute(q)
         except sqlite3.OperationalError as e:
            print "Error in SQLite3 for Query:\n" + q
            print "Error message: '%s'" % e
            
         q = SteamEntrySettings.CreateTableQuery()
         try: c.execute(q)
         except sqlite3.OperationalError as e:
            print "Error in SQLite3 for Query:\n" + q
            print "Error message: '%s'" % e
            
         q = EntryHistory.CreateTableQuery()
         try: c.execute(q)
         except sqlite3.OperationalError as e:
            print "Error in SQLite3 for Query:\n" + q
            print "Error message: '%s'" % e
         
         q = self.profile.InsertQuery()
         try: c.execute(q)
         except sqlite3.OperationalError as e:
            print "Error in SQLite3 for Query:\n" + q
            print "Error message: '%s'" % e
            
         for entry in self.centralWidget().lastManuallySortedEntries:
            entrySettings = EntrySettings.FromEntry(entry)
            q = entrySettings.InsertQuery()
            try: c.execute(q)
            except sqlite3.OperationalError as e:
               print "Error in SQLite3 for Query:\n" + q
               print "Error message: '%s'" % e
         
         for se in self.profile.steamGames:
            entrySettings = SteamEntrySettings.FromSteamEntry(se)
            q = entrySettings.InsertQuery()
            try: c.execute(q)
            except sqlite3.OperationalError as e:
               print "Error in SQLite3 for Query:\n" + q
               print "Error message: '%s'" % e
            
         db.commit()
         db.close()
         
   def SetIconSize(self, size):
      self.iconSize = size
      self.toolsBar.iconSizeComboBox.SetCurrentSize(size)
      self.settingsMenu.CheckIconSizeAction(size)

      self.centralWidget().SetIconSize(size)
      
      self.SaveProfile()
      
   def ShowStats(self):
      dlg = StatsOverviewDialog(self.centralWidget().entries, self, self.profile.steamGames)
      dlg.show()
      
   def SwitchProfile(self):
      pDlg = ProfileSelectionDialog(self)
      result = pDlg.exec_()
      if result == QtGui.QDialog.Rejected:
         return None
            
      elif result == QtGui.QDialog.Accepted:
         if pDlg.newProfile:
            self.SaveDefaultProfile(pDlg.profileName)
         name = pDlg.profileName
         
         # store as last profile
         codepage = 'utf-8'
         with codecs.open('lastprofile', 'w', codepage) as f:
            f.write("# -*- coding: %s -*-\n" % codepage)
            f.write(name)
         
         
         # save profile
         self.SaveProfile(DisableAutosave=True)
            
         # restart program
         QtGui.qApp.exit(MainWindow.RestartCode)
         

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
      QtGui.QMenu.__init__(self, "&Profile", parent)
      
      self.switchAction = QtGui.QAction("S&witch profile", self)
      self.settingsAction = QtGui.QAction("&Settings", self)
      self.libraryAction = QtGui.QAction("Manage &library", self)
      
      self.addAction(self.libraryAction)
      self.addSeparator()
      self.addAction(self.switchAction)
      self.addAction(self.settingsAction)
      
      self.InitConnections()
      
   def InitConnections(self):
      self.switchAction.triggered.connect(self.parent().SwitchProfile)
      self.libraryAction.triggered.connect(self.parent().ManageLibrary)
      
class FileMenu(QtGui.QMenu):
   def __init__(self, parent=None):
      QtGui.QMenu.__init__(self, "&File", parent)
      
      self.steamProfileAction = QtGui.QAction("Add &Steam profile", self)
      self.exitAction = QtGui.QAction("E&xit", self)
      
      self.addAction(self.steamProfileAction)
      self.addSeparator()
      self.addAction(self.exitAction)
      
      self.InitConnections()
      
   def InitConnections(self):
      self.steamProfileAction.triggered.connect(self.parent().ConnectToSteamProfile)
      self.exitAction.triggered.connect(self.parent().close)