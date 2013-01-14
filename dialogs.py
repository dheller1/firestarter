import os
import ctypes

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, pyqtSignal

from ctypes import byref
from win32api import *
try:
   from winxpgui import *
except ImportError:
   from win32gui import *
from win32gui_struct import *

import win32com.client
usr32 = ctypes.windll.user32


from widgets import IconSizeComboBox


class ChooseIconDialog(QtGui.QDialog):
   """ Dialog which loads icons from one or several files, displays them in a list widget, and allows to choose one of them.
       When called with exec_(), the call returns 'None' if Cancel was pressed, otherwise it returns a tuple of (filename,id)
       for the icon in 'filename' with id 'id'. """
   def __init__(self, parent=None, file=None, suggestions=False):
      QtGui.QDialog.__init__(self, parent)
      
      self.setWindowTitle("Choose icon")
      self.resize(600,380)
      
      self.basefile = file
      
      # create widgets
      self.okBtn = QtGui.QPushButton("&Ok", self)
      self.okBtn.setDefault(True)
      self.okBtn.clicked.connect(self.accept)
      self.okBtn.setEnabled(False)
      
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
      
      self.iconSizeComboBox = IconSizeComboBox(self)
      self.iconSizeComboBox.IconSizeChanged.connect(self.SetIconSize)
      
      # init layout
      buttonsLayout= QtGui.QHBoxLayout()
      buttonsLayout.addWidget(self.okBtn)
      buttonsLayout.addWidget(self.cancelBtn)
      buttonsLayout.addWidget(self.selectFileBtn)
      buttonsLayout.addWidget(self.countLabel)
      
      
      mainLayout = QtGui.QVBoxLayout(self)
      
      topLayout = QtGui.QHBoxLayout()
      if suggestions: topLayout.addWidget(QtGui.QLabel("Suggested icons:"))
      topLayout.addStretch(1)
      topLayout.addWidget(self.iconSizeComboBox)
      
      mainLayout.addLayout(topLayout)
      mainLayout.addWidget(self.iconsList)
      mainLayout.addLayout(buttonsLayout)
      
      self.setLayout(mainLayout)
            
      # fill icon list
      self.Fill(file, suggestions)
      
      self.iconsList.itemSelectionChanged.connect(self.SelectionChanged)
      
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
         
   def SelectionChanged(self):
      self.okBtn.setEnabled(len(self.iconsList.selectedItems())==1)
      
   def SetIconSize(self, size):
      self.iconsList.setIconSize(QtCore.QSize(size, size))
         
   def SuggestFiles(self, file):
      files = []
      dir = os.path.dirname(file)
      dirList =  os.listdir(dir)
      
      for f in dirList:
         if os.path.join(dir,f) != file and (f.endswith(".exe") or f.endswith(".dll") or f.endswith(".ico") or f.endswith(".bmp")):
            files.append(os.path.join(dir,f))
            
      return files