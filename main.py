#PyQt5 is a set of Python bindings for Qt libraries which can be used to create cross-platform applications. Below is a simple example of how to create a basic browser window using PyQt5.
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import sys

#browser window
def window():
    app =QApplication(sys.argv)
    win = QMainWindow()
   
    #xpos, ypos, width, height
    win.setGeometry(1000, 200, 1000, 500)
    
    #name of the window
    win.setWindowTitle("D browser")
    
    #code about label 
    label = QtWidgets.QLabel(win)
    label.setText("Hello in D browser")
    label.move(50, 50)
    #chromium engine to load the web page
    browser = QWebEngineView(win)
    browser.load(QUrl("https://www.google.com"))
    win.setCentralWidget(browser)
   
    #show the window
    win.show()
    sys.exit(app.exec_())

window()