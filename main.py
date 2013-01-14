'''
Created on 03.01.2013

@author: heller
'''

import sys

from ui import MainWindow
from PyQt4 import QtGui


def main():
   app = QtGui.QApplication(sys.argv)
   
   mainWnd = MainWindow()
   mainWnd.show()
   
   sys.exit(app.exec_())
   
if __name__=="__main__":
   main()