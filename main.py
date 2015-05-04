# -*- coding: utf-8 -*-
'''
Created on 03.01.2013

@author: heller
'''

import sys, os, win32com.client

from ui import MainWindow
from PyQt4 import QtGui
from util import flushLogfiles

def pidRunning(pid):
   '''Check for the existence of a process id.'''
   wmi = win32com.client.GetObject('winmgmts:')
   prc = wmi.ExecQuery('Select * from win32_process where ProcessId=%s' % pid)
   return (len(prc)>0)

def main():
   #============================================================================
   # check if the program is already running
   #============================================================================
   pid = str(os.getpid())
   pidfile = "~firestarter.pid"
   
   running = False
   
   if os.path.isfile(pidfile):         # pid file available?
      with open(pidfile, 'r') as pf:
         oldpid = pf.readlines()[0]
         if pidRunning(oldpid):   # process with pid still alive?
            running = True
   
   if running: sys.exit()
   else:
      with open(pidfile, 'w') as pf: pf.write(pid)
      
   #============================================================================
   # verify directory structure
   #============================================================================
   neededFolders = ("cache", "cache/icons", "cache/steam", "export")
   for folder in neededFolders:
      if not os.path.isdir(folder):
         os.makedirs(folder)

   #============================================================================
   # Start main program
   #============================================================================
   ret = MainWindow.RestartCode
   while ret == MainWindow.RestartCode:
      flushLogfiles(("parser.log","steamapi.log"), 'utf-8')
      
      app = QtGui.QApplication(sys.argv)
      # run program
      mainWnd = MainWindow()
      mainWnd.show()
      
      ret = app.exec_()
      
      del mainWnd
      del app

   #============================================================================
   # cleanup and exit
   #============================================================================
   os.remove(pidfile)
   sys.exit(ret)
   
if __name__=="__main__":
   main()