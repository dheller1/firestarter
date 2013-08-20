# -*- coding: utf-8 -*-

import os, copy

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, pyqtSignal

from util import formatTime

class IconSizeComboBox(QtGui.QComboBox):
   supportedIconSizes = (32, 48, 128, 256)
   textTemplate = "%ix%i px" 
   
   IconSizeChanged = pyqtSignal(int)
   
   def __init__(self, parent=None):
      QtGui.QComboBox.__init__(self, parent)
      
      self.addItem("16x16 px")
      for size in IconSizeComboBox.supportedIconSizes:
         self.addItem(IconSizeComboBox.textTemplate % (size, size))
      
      self.setCurrentIndex(4)
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
   SortByTimeSelected = pyqtSignal()
   
   manualTxt = "Manual sorting"
   byTitleTxt = "Sort by title"
   byTimeTxt ="Sort by playtime"
   
   def __init__(self, parent=None):
      QtGui.QComboBox.__init__(self, parent)
      
      self.addItem(SortModeComboBox.manualTxt)
      self.addItem(SortModeComboBox.byTitleTxt)
      self.addItem(SortModeComboBox.byTimeTxt)
      
      # connections
      self.currentIndexChanged.connect(self.CurrentIndexChangedSlot)
      
   def CurrentIndexChangedSlot(self):
      text = self.currentText()
      if str(text) == SortModeComboBox.manualTxt:
         self.ManualSortingSelected.emit()
      elif str(text) == SortModeComboBox.byTitleTxt:
         self.SortByTitleSelected.emit()
      elif str(text) == SortModeComboBox.byTimeTxt:
         self.SortByTimeSelected.emit()
         
   def SelectManualSorting(self):
      self.setCurrentIndex(0)
      
class ToolsToolbar(QtGui.QToolBar):
   def __init__(self, parent=None):
      QtGui.QToolBar.__init__(self, "Tools", parent)
      
      # init children
      self.totalTime = QtGui.QLabel("Total playtime: <b>Never played</b>")
      self.iconSizeComboBox = IconSizeComboBox()
      self.sortComboBox = SortModeComboBox()
      self.upBtn = QtGui.QPushButton()
      self.upBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-up-icon.png")))
      self.upBtn.setEnabled(False)
      
      self.downBtn = QtGui.QPushButton()
      self.downBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "Actions-arrow-down-icon.png")))
      self.downBtn.setEnabled(False)
      
      self.statsBtn = QtGui.QPushButton()
      self.statsBtn.setIcon(QtGui.QIcon(os.path.join("gfx", "stats.png")))
      
      # init layout
      dwWdg = QtGui.QWidget(self)
      dwWdg.setLayout(QtGui.QHBoxLayout())
      
      dwWdg.layout().addWidget(self.totalTime)
      dwWdg.layout().addWidget(self.statsBtn)
      dwWdg.layout().addStretch(1)
      dwWdg.layout().addWidget(self.sortComboBox)
      dwWdg.layout().addWidget(self.upBtn)
      dwWdg.layout().addWidget(self.downBtn)
      dwWdg.layout().addWidget(self.iconSizeComboBox)
      
      self.addWidget(dwWdg)
      
   def DisableDownButton(self):
      self.downBtn.setEnabled(False)
   
   def DisableUpButton(self):
      self.upBtn.setEnabled(False)
   
   def EnableButtons(self):
      self.upBtn.setEnabled(True)
      self.downBtn.setEnabled(True)

   def UpdatePlaytime(self, time):
      self.totalTime.setText("Total playtime: <b>%s</b>" % formatTime(time).replace('<', '&lt;'))
      
class AutoSelectAllLineEdit(QtGui.QLineEdit):
   """ Custom QLineEdit which automatically selects all text if clicked. """
   def __init__(self, text="", parent=None):
      QtGui.QLineEdit.__init__(self, text, parent)
      
   def mousePressEvent(self, e):
      QtGui.QWidget.mousePressEvent(self, e)
      self.selectAll()
      
class OverviewRenderArea(QtGui.QWidget):
   def __init__(self, entries, parent=None):
      QtGui.QWidget.__init__(self)
      
      self.entries = entries
      
      self.zoom = 1.
      self.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum)
      
      self.setBackgroundRole(QtGui.QPalette.Shadow)
      self.setAutoFillBackground(True)
      
      self.iconSize = 32
      self.fontSize = 12
      self.largeFontFactor = 1.72
      self.margin = 2
      self.vspace = 5
      self.border = 1
      
      self.numEntries = 20
      
      entryWidth = self.zoom * (600+2*self.margin + self.vspace + 2*self.border)
      self.setMinimumSize(entryWidth + 2*self.vspace, 40)
      
   def paintEvent(self, event):
      numEntries = min(self.numEntries, len(self.entries))
      # geometry calculations
      entryHeight = self.zoom * ( self.iconSize + 2*self.margin + 2*self.border)
      entryWidth = self.zoom * (600+2*self.margin + self.vspace + 2*self.border)
      
      fullRect = QtCore.QRect(0, 0, entryWidth+ 2*self.vspace, numEntries * (entryHeight+self.vspace) + self.vspace)
      innerRect = QtCore.QRect(self.margin + self.border, self.margin + self.border, entryWidth - 2*(self.margin+self.border), entryHeight-2*(self.margin+self.border))
      self.setMinimumSize(fullRect.size())
      
      # create painter, fonts, pens and brushes
      painter = QtGui.QPainter(self)
      
      labelFont = QtGui.QFont("Cambria", self.zoom*self.fontSize*self.largeFontFactor)
      labelFont.setBold(True)
      timeFont = QtGui.QFont("Calibri", self.zoom*self.fontSize)
      timeFont.setBold(False)
      textPen = QtGui.QPen(Qt.white)
      
      bgGrad = QtGui.QLinearGradient(QtCore.QPointF(0,0), QtCore.QPointF(0,fullRect.height()))
      bgGrad.setColorAt(0, QtGui.QColor(63,63,61))
      bgGrad.setColorAt(0.15, QtGui.QColor(55,55,55))
      bgGrad.setColorAt(1, QtGui.QColor(38,38,39))
      
      backgroundBrush = QtGui.QBrush(bgGrad)
      
      defaultPen = QtGui.QPen(QtGui.QColor(124,124,124))
      defaultBrush = QtGui.QBrush()
      painter.setPen(defaultPen)
      painter.setBrush(defaultBrush)
      
      barGrad = QtGui.QLinearGradient(QtCore.QPointF(0,0), QtCore.QPointF(innerRect.width(),0))
      barGrad.setColorAt(0, QtGui.QColor(138,138,138))
      barGrad.setColorAt(0.5, QtGui.QColor(110,110,110))
      barGrad.setColorAt(1, QtGui.QColor(75,75,75))
      
      barPen = QtGui.QPen(Qt.NoPen)
      barBrush = QtGui.QBrush(barGrad)
      
      
      # draw background
      painter.save()
      painter.setBrush(backgroundBrush)
      painter.setPen(Qt.NoPen)
      painter.drawRect(fullRect)
      painter.restore()

      painter.translate(self.vspace, self.vspace)
      
      tmax = max([e.totalTime for e in self.entries])
      
      iEntry = 0
      for entry in self.entries:
         if iEntry >= numEntries: break
         
         # begin painting
         if self.border != 0:
            painter.save()
            defaultPen.setWidth(self.border)
            borderRect = QtCore.QRect(0, 0, entryWidth, entryHeight)
            painter.drawRect(borderRect)
            painter.restore()
         
         barRect = copy.copy(innerRect)
         barRect.setLeft(barRect.left()+ self.iconSize + self.vspace)
         
         # playtime bar
         fillPct = entry.totalTime / tmax
         barRect.setWidth(max(1, fillPct * barRect.width()))

         painter.save()         
         painter.setPen(barPen)
         painter.setBrush(barBrush)
         painter.drawRect(barRect)
         painter.restore()
         
         # icon and title
         painter.save()
         painter.setFont(labelFont)
         painter.drawPixmap(innerRect.topLeft(), entry.icon.pixmap(self.iconSize, self.iconSize))
         painter.setPen(textPen)
         painter.drawText(innerRect.translated(self.iconSize+self.vspace, 0), Qt.AlignVCenter, entry.label)
         
         # playtime
         painter.setFont(timeFont)
         painter.drawText(innerRect, Qt.AlignRight | Qt.AlignBottom, formatTime(entry.totalTime)+ " played")
         painter.restore()
         
         painter.translate(0, entryHeight + self.vspace)
         
         iEntry += 1