#PyQt5 is a set of Python bindings for Qt libraries which can be used to create cross-platform applications. Below is a simple example of how to create a basic browser window using PyQt5.
import http
from turtle import title

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QToolBar, QAction, QLineEdit
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import sys
import json
import os

HOME_URL = QUrl.fromLocalFile(os.path.abspath("home.html"))

HISTORY_FILE = "history.json"
BOOKMARKS_FILE = "bookmarks.json"

class OrionBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(GALAXY_QSS)
        self.setWindowTitle("Orion Browser")
        self.setGeometry(100, 100, 1200, 800)

        self.init_storage()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)

        self.setCentralWidget(self.tabs)

        navbar = QToolBar()
        self.addToolBar(navbar)

        back_btn = QAction("◄", self)
        back_btn.triggered.connect(lambda: self.go_back())
        navbar.addAction(back_btn)

        forward_btn = QAction("►", self)
        forward_btn.triggered.connect(lambda: self.go_forward())
        navbar.addAction(forward_btn)

        reload_btn = QAction("⟳", self)
        reload_btn.triggered.connect(lambda: self.reload_page())
        navbar.addAction(reload_btn)

        add_tab_btn = QAction("+", self)
        add_tab_btn.triggered.connect(lambda: self.add_new_tab(QUrl("http://www.google.com")))
        navbar.addAction(add_tab_btn)

        bookmark_btn = QAction("★", self)
        bookmark_btn.triggered.connect(lambda: self.add_to_bookmarks())
        navbar.addAction(bookmark_btn)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navbar.addWidget(self.url_bar)

        history_btn = QAction("History", self)
        history_btn.triggered.connect(lambda: self.show_history())
        navbar.addAction(history_btn)

        self.add_new_tab(HOME_URL, "homepage")

    def init_storage(self):
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

        if not os.path.exists(BOOKMARKS_FILE):
            with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None:
            qurl = QUrl("http://www.google.com")

        browser = QWebEngineView()
        browser.setUrl(qurl)
        
        index = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url_bar(qurl, browser))
        browser.loadFinished.connect(lambda _, index=index, browser=browser: self.update_tab_title(index))

    def update_tab_title(self, index):
        browser = self.tabs.widget(index)
        if index != -1 and browser is not None:
            self.tabs.setTabText(index, browser.page().title())
            url = browser.url().toString()
            self.update_url_bar(QUrl(url), browser)

    def close_tab(self, index):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(index)

    def navigate_to_url(self):
        text = self.url_bar.text()
        if not text.startswith("http://") and not text.startswith("https://"):
            if "." in text and " " not in text:
                url = QUrl("https://" + text)
            else:
                url = QUrl(f"https://www.google.com/search?q={text}")
        else:
            url = QUrl(text)

        self.current_browser().setUrl(url)

    def update_url_bar(self, qurl, browser):
        if self.current_browser() == browser:
            self.url_bar.setText(qurl.toString())

    def tab_changed(self, index):
        browser = self.tabs.widget(index)
        if browser is not None:
            self.url_bar.setText(browser.url().toString())

    def go_back(self):
        if self.current_browser() is not None:
            self.current_browser().back()

    def go_forward(self):
        if self.current_browser() is not None:
            self.current_browser().forward()

    def reload_page(self):
        if self.current_browser() is not None:
            self.current_browser().reload()

    def add_to_bookmarks(self):
        try:
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                bookmarks = json.load(f)
                print("\n--- ⭐ BROWSER BOOKMARKS ---")
                for item in bookmarks:
                    print(f" - {item['title']}: {item['url']}")
        except Exception as e:
            print("Bookmarks error:", e)

    def save_to_history(self, title, url):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)

            history.append({"title": title, "url": url})

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("History error:", e)

GALAXY_QSS = """
QMainWindow, QWidget {
    background-color: #0b0720;      /* deep space */
    color: #e6dcff;
    font-family: 'Segoe UI';
    font-size: 14px;
}

QLineEdit {                          /* address bar */
    background-color: #1a1040;
    border: 2px solid #7b2ff7;
    border-radius: 14px;
    padding: 6px 14px;
    color: #ffffff;
    selection-background-color: #b57bff;
}
QLineEdit:focus { border: 2px solid #c77dff; }

QPushButton, QToolButton {
    background-color: #2a1766;
    border: 1px solid #7b2ff7;
    border-radius: 10px;
    padding: 6px 12px;
}
QPushButton:hover, QToolButton:hover { background-color: #7b2ff7; }
QPushButton:pressed, QToolButton:pressed { background-color: #5a1fc0; }

QToolBar { background: #120a30; border: none; spacing: 6px; padding: 4px; }

QTabWidget::pane { border: none; }
QTabBar::tab {
    background: #1a1040;
    color: #cbb8ff;
    padding: 8px 18px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #7b2ff7; color: white; }
QTabBar::tab:hover:!selected { background: #3a1f8a; }

QScrollBar:vertical { background: #0b0720; width: 10px; }
QScrollBar::handle:vertical { background: #7b2ff7; border-radius: 5px; }
"""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    QApplication.setApplicationName("Orion Browser")
    window = OrionBrowser()
    window.show()
    sys.exit(app.exec_())
