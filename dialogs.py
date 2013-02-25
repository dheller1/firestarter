# -*- coding: utf-8 -*-

import os
import ctypes
import time
import urllib

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

from widgets import IconSizeComboBox, AutoSelectAllLineEdit
from steamapi import SteamApi


class SteamProfileDialog(QtGui.QDialog):
   class enterUsernameWidget(QtGui.QWidget):
      def __init__(self, parent = None):
         QtGui.QWidget.__init__(self, parent)
         
         self.usernameLe = QtGui.QLineEdit(self)
         self.usernameLe.setFocus()
         dlgNavLay = QtGui.QHBoxLayout()
      
         self.nextBtn = QtGui.QPushButton("&Next >>", self)
         self.nextBtn.setDefault(True)
         self.nextBtn.clicked.connect(self.parent().UsernameEntered)
         #self.okBtn.setEnabled(False)
      
         self.cancelBtn = QtGui.QPushButton("&Cancel", self)
         self.cancelBtn.clicked.connect(self.parent().reject)
      
         dlgNavLay.addStretch(1)
         dlgNavLay.addWidget(self.cancelBtn)
         dlgNavLay.addWidget(self.nextBtn)
         
         layout = QtGui.QGridLayout()
         layout.addWidget(QtGui.QLabel("Please enter your Steam username (found in your profile URL):"), 0, 0, 1, 2)
         layout.addWidget(QtGui.QLabel("http://steamcommunity.com/id/"), 1, 0, QtCore.Qt.AlignRight)
         layout.addWidget(self.usernameLe, 1, 1)
         layout.addLayout(dlgNavLay, 3, 0, 1, 2)
         
         self.setLayout(layout)
         
   class confirmProfileWidget(QtGui.QWidget):
      def __init__(self, parent = None):
         QtGui.QWidget.__init__(self, parent)
         
         self.avatarLbl = QtGui.QLabel()
         self.nameLbl = QtGui.QLabel()
         self.steamIdLbl = QtGui.QLabel()
         self.lastOnlineLbl = QtGui.QLabel()
         
         layout = QtGui.QGridLayout()
         layout.addWidget(QtGui.QLabel("Is this the correct profile?"), 0, 0, 1, 2)
         layout.addWidget(self.avatarLbl, 1, 0, 3, 1, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
         layout.addWidget(self.nameLbl, 1, 1)
         layout.addWidget(self.steamIdLbl, 2, 1)
         layout.addWidget(self.lastOnlineLbl, 3, 1)
         
         layout.setRowStretch(1, 1)
         
         self.setLayout(layout)
         
      def Fill(self, playerSummary):
         avatar = QtGui.QPixmap(os.path.join('cache', '%s.jpg' % playerSummary.steamid))
         self.avatarLbl.setPixmap(avatar)
         self.nameLbl.setText(playerSummary.personaname)
         self.steamIdLbl.setText('Steam ID: %s' % playerSummary.steamid)
         self.lastOnlineLbl.setText('Last online: '+time.ctime(float(playerSummary.lastlogoff)))
   
   def __init__(self, parent=None):
      QtGui.QDialog.__init__(self, parent)
      
      self.setWindowTitle("Add Steam profile")
      
      self.confirmProfileWdg = SteamProfileDialog.confirmProfileWidget(self)
      self.enterUsernameWdg = SteamProfileDialog.enterUsernameWidget(self)
      
      self.setLayout(QtGui.QStackedLayout())
      self.layout().addWidget(self.enterUsernameWdg)
      self.layout().addWidget(self.confirmProfileWdg)
      
   def UsernameEntered(self):
      # try to fetch profile
      username = str(self.enterUsernameWdg.usernameLe.text())
      if len(username) == 0:
         QtGui.QMessageBox.critical(self, "Error", "Please enter a valid Steam username!")
         return
      
      steamapi = SteamApi()
      
      tries = 0
      steamid = None
      
      self.enterUsernameWdg.cancelBtn.setEnabled(False)
      self.enterUsernameWdg.nextBtn.setEnabled(False)
      
      #pd = QtGui.QProgressDialog("Requesting Steam ID ...", "&Cancel", 0, 2, self)
      #pd.setWindowModality(QtCore.Qt.WindowModal)
      #pd.show()
      
      pbLbl = QtGui.QLabel("Please wait a moment.\nRequesting Steam ID ...")
      pb = QtGui.QProgressBar(self.enterUsernameWdg)
      pb.setMaximum(3)
      
      self.enterUsernameWdg.layout().addWidget(pbLbl, 2, 0)
      self.enterUsernameWdg.layout().addWidget(pb, 2, 1)
      
      while steamid == None and tries <= 10:
         QtGui.qApp.processEvents()
         tries += 1
         pbLbl.setText("Please wait a moment.\nRequesting Steam ID ... (%i)" % tries)
         self.enterUsernameWdg.repaint()
         steamid = steamapi.GetSteamIdByUsername(username)
         
      if steamid == None:
         pb.hide()
         pbLbl.hide()
         QtGui.QMessageBox.critical(self, "Error", "Could not fetch profile information.\nPlease check your internet connection and/or try again later.")

      else:      
         pb.setValue(1)
         pbLbl.setText("Found profile %i!\nFetching profile summary ..." % steamid)
         QtGui.qApp.processEvents()
      
         self.playerSummary = steamapi.GetPlayerSummary(steamid)
      
         pb.setValue(2)
         pbLbl.setText("Received profile summary.\nDownloading your avatar ...")
         QtGui.qApp.processEvents()
         
         try:
            with open(os.path.join('cache', '%i.jpg' % steamid), 'wb') as localFile:
               avatarFile = urllib.urlopen(self.playerSummary.avatarmedium)
               localFile.write(avatarFile.read())
               avatarFile.close()
         except IOError:
            QtGui.QMessageBox.critical(self, "Error", "Could not download avatar.\nPlease check if the subfolder 'cache' is present.")
            self.reject()
            return
         
         pb.setValue(3)
         pbLbl.setText("Downloaded Avatar ... Proceeding.")
         QtGui.qApp.processEvents()
         time.sleep(0.6)
         
         # proceed to next dialog page
         self.layout().setCurrentWidget(self.confirmProfileWdg)
         self.confirmProfileWdg.Fill(self.playerSummary)
      
      self.enterUsernameWdg.nextBtn.setEnabled(True)
      self.enterUsernameWdg.cancelBtn.setEnabled(True)
      

class ChooseIconDialog(QtGui.QDialog):
   """ Dialog which loads icons from one or several files, displays them in a list widget, and allows to choose one of them.
       When called with exec_(), the call returns 'None' if Cancel was pressed, otherwise it returns a tuple of (filename,id)
       for the icon in 'filename' with id 'id'. """
   def __init__(self, parent=None, file=None, suggestions=False):
      QtGui.QDialog.__init__(self, parent)
      
      self.setWindowTitle("Choose icon")
      self.resize(600,380)
      
      self.basefile = file
      self.noIcon = False # only set true if 'No icon' is clicked
      
      # create widgets
      self.okBtn = QtGui.QPushButton("&Ok", self)
      self.okBtn.setDefault(True)
      self.okBtn.clicked.connect(self.accept)
      self.okBtn.setEnabled(False)
      
      self.noIconBtn = QtGui.QPushButton("&No icon", self)
      self.noIconBtn.clicked.connect(self.ReturnNoIcon)
      
      self.cancelBtn = QtGui.QPushButton("&Cancel", self)
      self.cancelBtn.clicked.connect(self.reject)
      self.cancelBtn.setFocus()
      
      self.selectFileBtn = QtGui.QPushButton("&Select file...", self)
      self.selectFileBtn.clicked.connect(self.SelectFile)
      
      self.countLabel = QtGui.QLabel("0 icons found.")
      
      size = QtCore.QSize(128,128)
      self.iconsList = QtGui.QListWidget(self)
      self.iconsList.setViewMode(QtGui.QListView.IconMode)
      self.iconsList.setIconSize(size)
      #self.iconsList.setGridSize(size)
      self.iconsList.setMovement(QtGui.QListView.Static)
      self.iconsList.itemDoubleClicked.connect(self.accept)
      
      self.iconSizeComboBox = IconSizeComboBox(self)
      self.iconSizeComboBox.IconSizeChanged.connect(self.SetIconSize)
      
      # init layout
      buttonsLayout= QtGui.QHBoxLayout()
      buttonsLayout.addWidget(self.okBtn)
      buttonsLayout.addWidget(self.cancelBtn)
      buttonsLayout.addWidget(self.noIconBtn)
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
      
      if result == QtGui.QDialog.Accepted and self.noIcon:
         return "", -1
      elif result == QtGui.QDialog.Accepted and len(self.iconsList.selectedItems())==1:
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
      
   def ReturnNoIcon(self):
      self.noIcon = True
      self.accept()
      
   def SelectFile(self):
      files = QtGui.QFileDialog.getOpenFileNames(self, "Select icon file(s):", os.path.dirname(self.basefile) if self.basefile else ".",\
                                                 "Files containing icons (*.exe *.dll *.ico *.bmp);;All files (*.*)" )
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
   

class EntryPropertiesDialog(QtGui.QDialog):
   def __init__(self, entry, parent=None):
      QtGui.QDialog.__init__(self, parent)
      
      self.setWindowTitle("Properties")
      #self.resize(300,500)
      
      self.entry = entry
      
      # dialog flags
      self.iconChanged = False       # icon update necessary
      
      # create widgets
      self.okBtn = QtGui.QPushButton("&Ok", self)
      self.okBtn.setDefault(True)
      self.okBtn.clicked.connect(self.accept)
      
      self.cancelBtn = QtGui.QPushButton("&Cancel", self)
      self.cancelBtn.clicked.connect(self.reject)
      
      
      self.labelLe = AutoSelectAllLineEdit(entry.label, self)
      self.filenameLe = AutoSelectAllLineEdit(entry.filename, self)
      self.chooseExecutable = QtGui.QPushButton(QtGui.QIcon(os.path.join("gfx", "folder-open-icon.png")), "")
      self.cmdLineArgsLe = AutoSelectAllLineEdit(entry.cmdLineArgs, self)
      self.workingDirLe = AutoSelectAllLineEdit(entry.workingDir, self)
      self.chooseWorkingDir = QtGui.QPushButton(QtGui.QIcon(os.path.join("gfx", "folder-open-icon.png")), "")
      
      iconTxt = "\"" + entry.iconPath + "\",%i" % entry.preferredIcon if entry.preferredIcon > -1 else "-"
      self.iconLe = AutoSelectAllLineEdit(iconTxt)
      self.chooseIcon = QtGui.QPushButton(QtGui.QIcon(os.path.join("gfx", "folder-open-icon.png")), "")
      
      # init layout
      buttonsLayout= QtGui.QHBoxLayout()
      buttonsLayout.addWidget(self.okBtn)
      buttonsLayout.addWidget(self.cancelBtn)
      
      formLayout = QtGui.QGridLayout()
      
      formLayout.addWidget(QtGui.QLabel("Name:"), 0, 0)
      formLayout.addWidget(self.labelLe, 0, 1, 1, 2)
      
      formLayout.addWidget(QtGui.QLabel("Executable:"), 1, 0)
      formLayout.addWidget(self.filenameLe, 1, 1, 1, 1)
      formLayout.addWidget(self.chooseExecutable, 1, 2, 1, 1)
      
      formLayout.addWidget(QtGui.QLabel("Additional arguments:"), 2, 0)
      formLayout.addWidget(self.cmdLineArgsLe, 2, 1, 1, 2)
      
      formLayout.addWidget(QtGui.QLabel("Working directory:"), 3, 0)
      formLayout.addWidget(self.workingDirLe, 3, 1, 1, 1)
      formLayout.addWidget(self.chooseWorkingDir, 3, 2, 1, 1)
      
      formLayout.addWidget(QtGui.QLabel("Icon:"), 4, 0)
      formLayout.addWidget(self.iconLe, 4, 1, 1, 1)
      formLayout.addWidget(self.chooseIcon, 4, 2, 1, 1)
      
      #formLayout.addRow("Name:", self.labelLe)
      #formLayout.addRow("Executable:", self.filenameLe)
      #formLayout.addRow("Additional arguments:", self.cmdLineArgsLe)
      #formLayout.addRow("Working directory:", self.workingDirLe)
      #formLayout.addRow("Icon path:", iconWdg)
      
      mainLayout = QtGui.QVBoxLayout()
      mainLayout.addLayout(formLayout)
      mainLayout.addLayout(buttonsLayout)
      
      self.setLayout(mainLayout)
      
      self.InitConnections()
      
   def exec_(self):
      """ If the icon has been changed, return the new icon path """
      result = QtGui.QDialog.exec_(self)
      
      if result == QtGui.QDialog.Accepted:
         self.entry.label = str(self.labelLe.text())
         self.entry.filename = str(self.filenameLe.text())
         self.entry.workingDir = str(self.workingDirLe.text())
         self.entry.cmdLineArgs = str(self.cmdLineArgsLe.text())
         
         if self.iconChanged:
            self.entry.iconPath = self.newIconPath
            self.entry.preferredIcon = self.newIconId
            self.entry.LoadIcon()
            self.entry.UpdateIcon.emit()
            
         self.entry.UpdateText.emit()
         self.entry.UpdateProfile.emit()
      
      return result
      
   def ChangeExecutable(self):
      file = QtGui.QFileDialog.getOpenFileName(self, "Choose executable:", self.filenameLe.text(), "Executable files (*.exe)")
      if file != "":
         self.filenameLe.setText(file)
         self.workingDirLe.setText(os.path.dirname(str(file)))
      
   def ChangeIcon(self):
      dlg = ChooseIconDialog(self, file=self.entry.iconPath, suggestions=True)
      result = dlg.exec_()
      
      if result == None: return
      else:
         path, id = result
         if self.entry.iconPath != path or self.entry.preferredIcon != id:
            self.newIconPath = path
            self.newIconId = id
            self.iconChanged = True
            self.changed = True
            iconTxt = "\"" + path + "\",%i" % id if id > -1 else "-"
            self.iconLe.setText(iconTxt)
            
   def ChangeWorkingDir(self):
      wd = QtGui.QFileDialog.getExistingDirectory(self, "Choose working directory:", self.workingDirLe.text())
      if wd != "":
         self.workingDirLe.setText(wd)
      
   def InitConnections(self):
      self.chooseIcon.clicked.connect(self.ChangeIcon)
      self.chooseExecutable.clicked.connect(self.ChangeExecutable)
      self.chooseWorkingDir.clicked.connect(self.ChangeWorkingDir)