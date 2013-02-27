# -*- coding: utf-8 -*-

import os
import ctypes
import time
import urllib
import threading

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
   FailedSteamIdQuery = pyqtSignal()
   FailedPlayerSummaryQuery = pyqtSignal()
   FailedAvatarDl = pyqtSignal()
   InvalidUserQuery = pyqtSignal()
   SuccessfulAvatarDl = pyqtSignal()
   SuccessfulSteamIdQuery = pyqtSignal(str)
   SuccessfulPlayerSummaryQuery = pyqtSignal(object)
   
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
      
         dlgNavLay.addWidget(self.cancelBtn)
         dlgNavLay.addStretch(1)
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
         
         self.nextBtn = QtGui.QPushButton("&Yes", self)
         self.nextBtn.setDefault(True)
         self.nextBtn.setFocus()
         self.nextBtn.clicked.connect(self.parent().accept)
         
         self.backBtn = QtGui.QPushButton("<< &Back", self)
         self.backBtn.clicked.connect(self.parent().BackToUsernameWdg)
         
         self.cancelBtn = QtGui.QPushButton("&Cancel", self)
         self.cancelBtn.clicked.connect(self.parent().reject)
      
         dlgNavLay = QtGui.QHBoxLayout()
         dlgNavLay.addWidget(self.cancelBtn)
         dlgNavLay.addStretch(1)
         dlgNavLay.addWidget(self.backBtn)
         dlgNavLay.addWidget(self.nextBtn)
         
         layout = QtGui.QGridLayout()
         layout.addWidget(QtGui.QLabel("Connect to profile?"), 0, 0, 1, 2)
         layout.addWidget(self.avatarLbl, 1, 0, 3, 1, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
         layout.addWidget(self.nameLbl, 1, 1)
         layout.addWidget(self.steamIdLbl, 2, 1)
         layout.addWidget(self.lastOnlineLbl, 3, 1)
         layout.addLayout(dlgNavLay, 4, 0, 1, 2)
         
         layout.setRowStretch(1, 1)
         
         self.setLayout(layout)
         
      def Fill(self, username, playerSummary):
         avatar = QtGui.QPixmap(os.path.join('cache', '%s.jpg' % playerSummary.steamid))
         if avatar.isNull():
            avatar = QtGui.QPixmap(os.path.join('gfx', 'noavatar.png'))
         self.avatarLbl.setPixmap(avatar)
         self.nameLbl.setText('<b>%s</b> (%s)' % (username, playerSummary.personaname))
         self.steamIdLbl.setText('Steam ID: <b>%s</b>' % playerSummary.steamid)
         
         if int(playerSummary.personastate) == 0:
            timeStr = time.strftime('%a %d. %b %Y, %H:%M', time.localtime(float(playerSummary.lastlogoff)))
            self.lastOnlineLbl.setText('Last online: <b>%s</b>' % timeStr)
         else:
            self.lastOnlineLbl.setText('<span style="color: green;"><b>Currently online</b></span>')
   
   def __init__(self, parent=None):
      QtGui.QDialog.__init__(self, parent)
      
      self.steamapi = SteamApi()
      self.tries = 0
            
      self.setWindowTitle("Add Steam profile")
      #self.resize(370,180)
      
      self.confirmProfileWdg = SteamProfileDialog.confirmProfileWidget(self)
      self.enterUsernameWdg = SteamProfileDialog.enterUsernameWidget(self)
      
      self.setLayout(QtGui.QStackedLayout())
      self.layout().addWidget(self.enterUsernameWdg)
      self.layout().addWidget(self.confirmProfileWdg)
      
      # init connections
      self.FailedSteamIdQuery.connect(self.RetrySteamIdQuery)
      self.FailedPlayerSummaryQuery.connect(self.NoPlayerSummaryFound)
      self.FailedAvatarDl.connect(self.AvatarNotReceived)
      self.InvalidUserQuery.connect(self.InvalidUsernameDetected)
      self.SuccessfulSteamIdQuery.connect(self.SteamIdReceived)
      self.SuccessfulPlayerSummaryQuery.connect(self.PlayerSummaryReceived)
      self.SuccessfulAvatarDl.connect(self.AvatarReceived)
      
   def __del__(self):
      self.steamapi.__del__()
      
   def reject(self):
      # disconnect all connections to not respond to any threads still working when they finish
      self.FailedSteamIdQuery.disconnect()
      self.FailedPlayerSummaryQuery.disconnect()
      self.FailedAvatarDl.disconnect()
      self.InvalidUserQuery.disconnect()
      self.SuccessfulSteamIdQuery.disconnect()
      self.SuccessfulPlayerSummaryQuery.disconnect()
      self.SuccessfulAvatarDl.disconnect()
      
      QtGui.QDialog.reject(self)
      
      # shut down query thread, if it is still working
      # --- not needed anymore, as this dialog is a member of the MainWindow object,
      # --- it will be kept until closing the program, so the already disconnected
      # --- threads have enough time to finish whatever they are currently doing.
      
      #if hasattr(self, 'queryThread') and self.queryThread.isAlive():
      #   self.queryThread.join(0.1)
      #   if self.queryThread.isAlive():
      #      raise Exception('SteamProfileDialog could not shut down query thread!')
      
   def Thread_DownloadAvatar(self, url, steamid):
      try:
         with open(os.path.join('cache', '%i.jpg' % steamid), 'wb') as localFile:
            avatarFile = urllib.urlopen(url)
            localFile.write(avatarFile.read())
            avatarFile.close()
      except IOError:
         self.FailedAvatarDl.emit()
         return

      self.SuccessfulAvatarDl.emit()
      
   def Thread_GetSteamIdByUsername(self, username):
      # start query ... this takes a while
      steamid = self.steamapi.GetSteamIdByUsername(username)
      
      if steamid is None:
         self.FailedSteamIdQuery.emit()
      elif steamid is SteamApi.ERR_INVALID_USER:
         self.InvalidUserQuery.emit()
      else:
         self.SuccessfulSteamIdQuery.emit(str(steamid))
   
   def Thread_GetPlayerSummary(self, steamid):
      # start query ... this might take a bit
      playerSummary = self.steamapi.GetPlayerSummary(steamid)
      
      if playerSummary is None:
         self.FailedPlayerSummaryQuery.emit()
      else:
         self.SuccessfulPlayerSummaryQuery.emit(playerSummary)
         
   def BackToUsernameWdg(self):
      self.CancelSteamQueries()
      self.layout().setCurrentWidget(self.enterUsernameWdg)
      
   def CancelSteamQueries(self):
      self.progressBar.hide()
      self.pbLbl.hide()
      self.enterUsernameWdg.nextBtn.setEnabled(True)
      self.enterUsernameWdg.cancelBtn.setEnabled(True)
      self.enterUsernameWdg.usernameLe.setEnabled(True)
      
   def RetrySteamIdQuery(self):
      if self.tries >= 10:
         self.CancelSteamQueries()
         QtGui.QMessageBox.critical(self, "Error", "Could not fetch profile information.\nPlease check your internet connection and/or try again later.")
         return

      self.progressBar.setValue(self.tries)
      self.pbLbl.setText("Please wait a moment.\nRequesting Steam ID ... (%i)" % self.tries)
      self.tries += 1
      
      self.queryThread = threading.Thread(target=self.Thread_GetSteamIdByUsername, args=(self.username,))
      self.queryThread.start()
      
   def SteamIdReceived(self, steamid):
      self.progressBar.setValue(10)
      self.pbLbl.setText("Found profile %s!\nFetching profile summary ..." % steamid)
      
      self.steamId = int(steamid)
      
      # start player summary query
      self.queryThread = threading.Thread(target=self.Thread_GetPlayerSummary, args=(int(steamid),))
      self.queryThread.start()
      
   def NoPlayerSummaryFound(self):
      result = QtGui.QMessageBox.critical(self, "Error", "Could not find player information for steam ID %i." % self.steamId, QtGui.QMessageBox.Retry | QtGui.QMessageBox.Cancel)
      if result == QtGui.QMessageBox.Retry:
         self.tries = 0
         self.RetrySteamIdQuery
         
      elif result == QtGui.QMessageBox.Cancel:
         self.CancelSteamQueries()
   
   def InvalidUsernameDetected(self):
      QtGui.QMessageBox.critical(self, "Error", "Steam did not return a profile for username %s.\nPlease check the username and try again." % self.username)
      self.CancelSteamQueries()
      self.enterUsernameWdg.usernameLe.selectAll()
      self.enterUsernameWdg.usernameLe.setFocus()
   
   def PlayerSummaryReceived(self, playerSummary):
      self.progressBar.setValue(20)
      self.pbLbl.setText("Received profile summary.\nDownloading avatar ...")
      
      self.playerSummary = playerSummary
      
      self.queryThread = threading.Thread(target=self.Thread_DownloadAvatar, args=(playerSummary.avatarmedium, self.steamId))
      self.queryThread.start()
      
   def AvatarReceived(self):
      self.progressBar.setValue(25)
      self.pbLbl.setText("Downloaded Avatar ... Proceeding.")
      QtGui.qApp.processEvents()
      time.sleep(0.6)
      
      # proceed to next dialog page
      self.layout().setCurrentWidget(self.confirmProfileWdg)
      self.confirmProfileWdg.Fill(self.username, self.playerSummary)
      
      self.enterUsernameWdg.nextBtn.setEnabled(True)
      self.enterUsernameWdg.cancelBtn.setEnabled(True)
      
   def AvatarNotReceived(self):
      result = QtGui.QMessageBox.warning(self, "Warning", "Unable to download avatar. Please check if the folder 'cache' exists in your FireStarter directory.", QtGui.QMessageBox.Retry | QtGui.QMessageBox.Ignore | QtGui.QMessageBox.Cancel)
      
      if result == QtGui.QMessageBox.Retry:
         # try again
         self.queryThread = threading.Thread(target=self.Thread_DownloadAvatar, args=(self.playerSummary.avatarmedium, self.steamId))
         self.queryThread.start()
      
      elif result == QtGui.QMessageBox.Ignore:
         # proceed to next dialog page
         self.layout().setCurrentWidget(self.confirmProfileWdg)
         self.confirmProfileWdg.Fill(self.username, self.playerSummary)
         
         self.enterUsernameWdg.nextBtn.setEnabled(True)
         self.enterUsernameWdg.cancelBtn.setEnabled(True)
      
      elif result == QtGui.QMessageBox.Cancel:
         self.CancelSteamQueries()
         
      return
      
   def UsernameEntered(self):
      # try to fetch profile
      self.username = str(self.enterUsernameWdg.usernameLe.text())
      if len(self.username) == 0:
         QtGui.QMessageBox.critical(self, "Error", "Please enter a valid Steam username!")
         return
      
      self.tries = 0
      
      #self.enterUsernameWdg.cancelBtn.setEnabled(False)
      self.enterUsernameWdg.nextBtn.setEnabled(False)
      self.enterUsernameWdg.usernameLe.setEnabled(False)
      
      self.pbLbl = QtGui.QLabel("Please wait a moment.\nRequesting Steam ID ... (1)")
      self.progressBar = QtGui.QProgressBar(self.enterUsernameWdg)
      self.progressBar.setMaximum(30) # 0-10 = 10 tries of receiving steam ID, 10-20 = Summary, 20-25 = Avatar, 25-30 = finished
      
      self.enterUsernameWdg.layout().addWidget(self.pbLbl, 2, 0)
      self.enterUsernameWdg.layout().addWidget(self.progressBar, 2, 1)
      
      # start query thread and return, waiting for the Thread's finished signal
      self.tries += 1
      self.queryThread = threading.Thread(target=self.Thread_GetSteamIdByUsername, args=(self.username,))
      self.queryThread.start()
      
      return
      

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