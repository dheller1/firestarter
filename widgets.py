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