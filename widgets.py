# -*- coding: utf-8 -*-

import os

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, pyqtSignal


class IconSizeComboBox(QtGui.QComboBox):
   supportedIconSizes = (32, 48, 128, 256)
   textTemplate = "%ix%i px" 
   
   IconSizeChanged = pyqtSignal(int)
   
   def __init__(self, parent=None):
      QtGui.QComboBox.__init__(self, parent)
      
      self.addItem("16x16 px")
      for size in IconSizeComboBox.supportedIconSizes:
         self.addItem(IconSizeComboBox.textTemplate % (size, size))
         
      self.currentIndexChanged.connect(self.CurrentIndexChangedSlot)
         
   def CurrentIndexChangedSlot(self, index):
      i = self.currentIndex()
      if i == 0: self.IconSizeChanged.emit(16)
      else: self.IconSizeChanged.emit(IconSizeComboBox.supportedIconSizes[i-1])
         
   def SetCurrentSize(self, size):
      if size == 16:
         self.setCurrentIndex(0)
      else:
         text = IconSizeComboBox.textTemplate %(size,size)
         self.setCurrentIndex(self.findText(text))
         
class SortModeComboBox(QtGui.QComboBox):
   ManualSortingSelected = pyqtSignal()
   SortByTitleSelected = pyqtSignal()
   
   manualTxt = "Manual sorting"
   byTitleTxt = "Sort by title"
   
   def __init__(self, parent=None):
      QtGui.QComboBox.__init__(self, parent)
      
      self.addItem(SortModeComboBox.manualTxt)
      self.addItem(SortModeComboBox.byTitleTxt)
      
      # connections
      self.currentIndexChanged.connect(self.CurrentIndexChangedSlot)
      
   def CurrentIndexChangedSlot(self):
      text = self.currentText()
      if str(text) == SortModeComboBox.manualTxt:
         self.ManualSortingSelected.emit()
      elif str(text) == SortModeComboBox.byTitleTxt:
         self.SortByTitleSelected.emit()
      
class ToolsToolbar(QtGui.QToolBar):
   def __init__(self, parent=None):
      QtGui.QToolBar.__init__(self, "Tools", parent)
      
      # init children
      self.iconSizeComboBox = IconSizeComboBox()
      self.sortComboBox = SortModeComboBox()
      self.upBtn = QtGui.QPushButton()
      self.upBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-up-icon.png")))
      
      self.downBtn = QtGui.QPushButton()
      self.downBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-down-icon.png")))
      
      # init layout
      dwWdg = QtGui.QWidget(self)
      dwWdg.setLayout(QtGui.QHBoxLayout())
      
      dwWdg.layout().addStretch(1)
      dwWdg.layout().addWidget(self.sortComboBox)
      dwWdg.layout().addWidget(self.upBtn)
      dwWdg.layout().addWidget(self.downBtn)
      dwWdg.layout().addWidget(self.iconSizeComboBox)
      
      self.addWidget(dwWdg)
      
   def EnableButtons(self):
      self.upBtn.setEnabled(True)
      self.downBtn.setEnabled(True)
      
   def DisableDownButton(self):
      self.downBtn.setEnabled(False)
   
   def DisableUpButton(self):
      self.upBtn.setEnabled(False)
         
class AutoSelectAllLineEdit(QtGui.QLineEdit):
   """ Custom QLineEdit which automatically selects all text if clicked. """
   def __init__(self, text="", parent=None):
      QtGui.QLineEdit.__init__(self, text, parent)
      
   def mousePressEvent(self, e):
      QtGui.QWidget.mousePressEvent(self, e)
      self.selectAll()