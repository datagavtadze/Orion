# Orion Browser
# This file builds a small web browser with PyQt5 (Python + Qt).
# PyQt5 lets Python create windows, buttons, and a Chromium web view.

# --- built-in Python libraries ---
import atexit        # run cleanup when the app closes normally
import json          # read/write history and bookmarks as JSON files
import os            # file paths, folders, environment variables
import shutil        # copy old history files into the new data folder
import sys           # command-line args and the process (exit, exception hook)
import traceback     # print a full error if something crashes
from datetime import datetime              # timestamps for history entries
from urllib.parse import parse_qs, unquote, urlparse  # pull search text out of Google URLs

def running_frozen():
    # True when this is a packaged app (.exe / frozen binary), not "python main.py".
    return getattr(sys, "frozen", False)


def app_dir():
    # Folder of the .exe (packaged) or of main.py (development).
    if running_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    # PyInstaller unpacks bundled files (home.html) into sys._MEIPASS.
    if running_frozen() and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return app_dir()


def find_home_html():
    # Find the homepage in every layout: source folder, .exe bundle, .deb / .rpm install.
    override = os.environ.get("ORION_HOME_HTML", "").strip()
    candidates = [
        override,
        os.path.join(resource_dir(), "home.html"),
        os.path.join(app_dir(), "home.html"),
        os.path.join(app_dir(), "share", "orion-browser", "home.html"),
        os.path.join(os.path.dirname(app_dir()), "share", "orion-browser", "home.html"),
        "/usr/share/orion-browser/home.html",
        "/usr/local/share/orion-browser/home.html",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return os.path.join(resource_dir(), "home.html")


BASE_DIR = app_dir()
HISTORY_LIMIT = 500  # keep only the newest 500 history entries
USE_SOFTWARE_RENDERING = False  # True on weak/broken GPUs after a crash


def user_data_dir():
    # Writable place for history, cache, and crash flags on every OS.
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "OrionBrowser")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/OrionBrowser")
    root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(root, "orion-browser")


DATA_DIR = user_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")
CRASH_SENTINEL = os.path.join(DATA_DIR, "did_not_exit_cleanly")
GPU_BROKEN_FLAG = os.path.join(DATA_DIR, "use_software_gpu")


def env_on(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def configure_environment():
    """Tune Qt/Chromium for this PC before Qt libraries load."""
    global USE_SOFTWARE_RENDERING

    # Sharp UI on HiDPI / Retina screens (Windows, macOS, Linux).
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    # Qt5 WebEngine is unstable on native Wayland. Use XWayland on Linux only.
    # Never set xcb on Windows or macOS — that would prevent the app from starting.
    if sys.platform.startswith("linux"):
        if os.environ.get("WAYLAND_DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
            os.environ["QT_QPA_PLATFORM"] = "xcb"

    # Last run died mid-start -> treat GPU as unsafe next time.
    if os.path.exists(CRASH_SENTINEL):
        open(GPU_BROKEN_FLAG, "a").close()
    open(CRASH_SENTINEL, "a").close()  # removed on a clean shutdown

    USE_SOFTWARE_RENDERING = env_on("ORION_SAFE_MODE") or os.path.exists(GPU_BROKEN_FLAG)

    flags = []
    if USE_SOFTWARE_RENDERING:
        # Slow but works on almost every GPU/driver.
        flags.extend(["--disable-gpu", "--disable-gpu-compositing"])
    else:
        # Faster path when the graphics driver is healthy.
        flags.append("--enable-gpu-rasterization")

    flags.append("--disable-gpu-sandbox")
    flags.append("--disable-background-networking")
    flags.append("--disk-cache-size=83886080")  # 80 MB cache, avoids filling small disks

    # Chromium refuses its sandbox when running as root (some Linux setups).
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags.extend(["--no-sandbox", "--disable-setuid-sandbox"])

    if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


def mark_clean_exit():
    # Reaching here means the window closed normally, not a GPU crash.
    try:
        if os.path.exists(CRASH_SENTINEL):
            os.remove(CRASH_SENTINEL)
    except OSError:
        pass


configure_environment()
atexit.register(mark_clean_exit)

# --- Qt widgets used for the window UI ---
try:
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QToolBar,
        QVBoxLayout,
    )
    from PyQt5.QtCore import Qt, QUrl
except ImportError:
    sys.stderr.write(
        "PyQt5 is missing.\n"
        "  pip install PyQt5 PyQtWebEngine\n"
        "  Fedora: sudo dnf install python3-qt5 python3-qt5-webengine\n"
    )
    sys.exit(1)

try:
    from PyQt5.QtWebEngineWidgets import (
        QWebEngineProfile,
        QWebEngineSettings,
        QWebEngineView,
    )
except ImportError:
    sys.stderr.write(
        "Qt WebEngine is missing (needed to show web pages).\n"
        "  pip install PyQtWebEngine\n"
        "  Fedora: sudo dnf install python3-qt5-webengine\n"
    )
    sys.exit(1)


def show_error(exc_type, exc_value, exc_tb):
    # Print Python exceptions that happen inside Qt (otherwise they can vanish).
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = show_error

HOME_HTML = find_home_html()
HOME_PAGE_URL = QUrl.fromLocalFile(HOME_HTML)


def migrate_old_json():
    # Keep using history/bookmarks if they still live next to main.py.
    for name, dest in (("history.json", HISTORY_FILE), ("bookmarks.json", BOOKMARKS_FILE)):
        old = os.path.join(BASE_DIR, name)
        if os.path.exists(old) and not os.path.exists(dest):
            try:
                shutil.copy2(old, dest)
            except OSError:
                pass


def configure_webengine():
    """Put Chromium cache in a writable folder and turn off extra work."""
    cache_dir = os.path.join(DATA_DIR, "cache")
    storage_dir = os.path.join(DATA_DIR, "storage")
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    profile = QWebEngineProfile.defaultProfile()
    profile.setCachePath(cache_dir)
    profile.setPersistentStoragePath(storage_dir)
    profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
    profile.setHttpCacheMaximumSize(80 * 1024 * 1024)

    settings = QWebEngineSettings.defaultSettings()
    settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
    settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
    settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
    settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebGLEnabled, not USE_SOFTWARE_RENDERING)
    settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, not USE_SOFTWARE_RENDERING)


def search_query_from_url(url):
    """If this URL is a Google search, return the typed query. Else return ''."""
    parsed = urlparse(url)  # split url into host, path, query string
    host = (parsed.netloc or "").lower()
    # Example: https://www.google.com/search?q=cats
    if "google." in host and parsed.path.startswith("/search"):
        values = parse_qs(parsed.query).get("q", [])  # get the q= parameter
        if values:
            # Convert %20 / + into a readable phrase.
            return unquote(values[0]).replace("+", " ").strip()
    return ""


def load_json_list(path):
    """Open a JSON file and return a list. If missing or broken, return []."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_json_list(path, data):
    """Write a Python list to disk as pretty JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class OrionBrowser(QMainWindow):
    """The main browser window: tabs, toolbar, address bar, history."""

    def __init__(self):
        super().__init__()  # create the QMainWindow
        self.setStyleSheet(GALAXY_QSS)          # purple "galaxy" look
        self.setWindowTitle("Orion Browser")    # text in the title bar
        self.fit_to_screen()                    # size the window to this monitor

        self.init_storage()  # make sure history.json / bookmarks.json exist

        # Tab strip in the center of the window.
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)   # simpler tab look
        self.tabs.setTabsClosable(True)   # show an X on each tab
        self.tabs.tabCloseRequested.connect(self.close_tab)     # X clicked
        self.tabs.currentChanged.connect(self.on_tab_changed)  # another tab selected
        self.setCentralWidget(self.tabs)

        # Top toolbar (back, forward, reload, +, star, url, history).
        navbar = QToolBar()
        self.addToolBar(navbar)

        back_btn = QAction("◄", self)
        back_btn.triggered.connect(lambda: self.go_back())  # previous page
        navbar.addAction(back_btn)

        forward_btn = QAction("►", self)
        forward_btn.triggered.connect(lambda: self.go_forward())  # next page
        navbar.addAction(forward_btn)

        reload_btn = QAction("⟳", self)
        reload_btn.triggered.connect(lambda: self.reload_page())  # refresh
        navbar.addAction(reload_btn)

        add_tab_btn = QAction("+", self)
        add_tab_btn.triggered.connect(lambda: self.add_new_tab(HOME_PAGE_URL, "New Tab"))
        navbar.addAction(add_tab_btn)

        self.bookmark_btn = QAction("☆", self)
        self.bookmark_btn.setToolTip("Add bookmark")
        self.bookmark_btn.triggered.connect(self.toggle_bookmark)
        navbar.addAction(self.bookmark_btn)

        self.url_bar = QLineEdit()  # address / search box
        self.url_bar.returnPressed.connect(self.navigate_to_url)  # Enter key
        navbar.addWidget(self.url_bar)

        bookmarks_btn = QAction("Bookmarks", self)
        bookmarks_btn.triggered.connect(self.show_bookmarks)
        navbar.addAction(bookmarks_btn)

        history_btn = QAction("History", self)
        history_btn.triggered.connect(self.show_history)
        navbar.addAction(history_btn)

        self.statusBar().showMessage("Ready")

        # Open the first tab on the local homepage.
        self.add_new_tab(HOME_PAGE_URL, "homepage")
        self.update_bookmark_star()

    def fit_to_screen(self):
        # 1920x1080 does not fit laptops or small monitors. Use ~85% of this screen.
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1024, 700)
            return
        area = screen.availableGeometry()
        width = max(800, min(int(area.width() * 0.85), area.width() - 24))
        height = max(560, min(int(area.height() * 0.85), area.height() - 24))
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())

    def init_storage(self):
        migrate_old_json()
        # Create empty JSON files the first time the browser runs.
        for path in (HISTORY_FILE, BOOKMARKS_FILE):
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump([], f)

    def current_browser(self):
        # The QWebEngineView inside the tab you are looking at.
        return self.tabs.currentWidget()

    def add_new_tab(self, qurl=None, label="New Tab"):
        # If no valid URL was given, open the homepage.
        if qurl is None or not isinstance(qurl, QUrl):
            qurl = HOME_PAGE_URL

        browser = QWebEngineView()  # one Chromium page
        browser.setUrl(qurl)

        index = self.tabs.addTab(browser, label)  # add it as a tab
        self.tabs.setCurrentIndex(index)          # switch to that tab

        # Keep the address bar in sync when this tab's URL changes.
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url_bar(qurl, browser))
        # When the page finishes, update the tab title and save history.
        browser.loadFinished.connect(lambda ok, browser=browser: self.on_page_loaded(ok, browser))

    def on_page_loaded(self, ok, browser):
        # ok is False if the page failed to load.
        if not ok or browser is None:
            return

        index = self.tabs.indexOf(browser)  # which tab this page belongs to
        title = browser.page().title() or browser.url().toString()
        if index != -1:
            self.tabs.setTabText(index, title)           # tab label = page title
            self.update_url_bar(browser.url(), browser)  # address bar = page url

        self.save_to_history(title, browser.url().toString())

    def close_tab(self, index):
        # Do not close the last remaining tab.
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(index)

    def navigate_to_url(self):
        # User pressed Enter in the address bar.
        text = self.url_bar.text()
        if not text.startswith("http://") and not text.startswith("https://"):
            if "." in text and " " not in text:
                url = QUrl("https://" + text)  # looks like a site: example.com
            else:
                url = QUrl(f"https://www.google.com/search?q={text}")  # treat as search
        else:
            url = QUrl(text)  # already a full URL

        self.current_browser().setUrl(url)

        # If this was a Google search, store it in search history right away.
        query = search_query_from_url(url.toString())
        if query:
            self.save_to_history(query, url.toString(), kind="search", query=query)

    def update_url_bar(self, qurl, browser):
        # Only change the address bar if THIS tab is the one you are viewing.
        if self.current_browser() == browser:
            self.url_bar.setText(qurl.toString())
            self.update_bookmark_star()

    def on_tab_changed(self, index):
        # Switching tabs: show that tab's URL in the address bar.
        browser = self.tabs.widget(index)
        if browser is not None:
            self.url_bar.setText(browser.url().toString())
            self.update_bookmark_star()

    def go_back(self):
        if self.current_browser() is not None:
            self.current_browser().back()

    def go_forward(self):
        if self.current_browser() is not None:
            self.current_browser().forward()

    def reload_page(self):
        if self.current_browser() is not None:
            self.current_browser().reload()

    def current_page_info(self):
        browser = self.current_browser()
        if browser is None:
            return "", ""
        url = browser.url().toString().strip()
        title = (browser.page().title() or url).strip()
        return title, url

    def is_bookmarked(self, url):
        return any((item.get("url") or "") == url for item in load_json_list(BOOKMARKS_FILE))

    def update_bookmark_star(self):
        _, url = self.current_page_info()
        saved = bool(url) and self.is_bookmarked(url)
        self.bookmark_btn.setText("★" if saved else "☆")
        self.bookmark_btn.setToolTip("Remove bookmark" if saved else "Add bookmark")

    def toggle_bookmark(self):
        # Star: save this page, or remove it if it is already bookmarked.
        title, url = self.current_page_info()
        if not url or url in ("about:blank",) or url.startswith(("chrome:", "data:", "javascript:")):
            self.statusBar().showMessage("Nothing to bookmark on this page", 2500)
            return

        try:
            bookmarks = load_json_list(BOOKMARKS_FILE)
            existing = [item for item in bookmarks if item.get("url") == url]
            if existing:
                bookmarks = [item for item in bookmarks if item.get("url") != url]
                save_json_list(BOOKMARKS_FILE, bookmarks)
                self.statusBar().showMessage("Bookmark removed", 2500)
            else:
                bookmarks.append({
                    "title": title or url,
                    "url": url,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                save_json_list(BOOKMARKS_FILE, bookmarks)
                self.statusBar().showMessage("Page bookmarked", 2500)
        except Exception as e:
            self.statusBar().showMessage("Bookmarks error: " + str(e), 4000)

        self.update_bookmark_star()

    def show_bookmarks(self):
        # Open the Bookmarks popup. If the user picks a URL, load it in this tab.
        dialog = BookmarksDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_url:
            self.current_browser().setUrl(QUrl(dialog.selected_url))
        self.update_bookmark_star()

    def show_history(self):
        # Open the History popup. If the user picks a URL, load it in this tab.
        dialog = HistoryDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_url:
            self.current_browser().setUrl(QUrl(dialog.selected_url))

    def save_to_history(self, title, url, kind=None, query=""):
        # Store one visit or search into history.json.
        url = (url or "").strip()
        # Skip blank pages and the local homepage.
        if not url or url in ("about:blank", HOME_PAGE_URL.toString()):
            return
        if url.startswith(("chrome:", "data:", "javascript:")):
            return

        query = query or search_query_from_url(url)
        if kind is None:
            kind = "search" if query else "page"  # Google URL = search, otherwise a page

        entry = {
            "title": title or query or url,  # what to show in the list
            "url": url,                      # where to go if opened again
            "kind": kind,                    # "search" or "page"
            "query": query,                  # search text, if any
            "visited_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        try:
            history = load_json_list(HISTORY_FILE)
            # If you refresh the same URL, update the last row instead of duplicating.
            if history and history[-1].get("url") == url:
                history[-1] = entry
            else:
                history.append(entry)
            save_json_list(HISTORY_FILE, history[-HISTORY_LIMIT:])
        except Exception as e:
            print("History error:", e)


class HistoryDialog(QDialog):
    """Popup that lists searches and visited pages."""

    def __init__(self, parent):
        super().__init__(parent)
        self.selected_url = ""  # filled when the user opens an item
        self.setWindowTitle("History")
        self.resize(720, 560)
        self.setStyleSheet(GALAXY_QSS)

        layout = QVBoxLayout(self)  # stack widgets from top to bottom

        heading = QLabel("History")
        heading.setStyleSheet("font-size: 22px; font-weight: 600; padding: 4px 0;")
        layout.addWidget(heading)

        self.filter_bar = QLineEdit()
        self.filter_bar.setPlaceholderText("Filter visits and searches...")
        self.filter_bar.textChanged.connect(self.populate_lists)  # re-filter as you type
        layout.addWidget(self.filter_bar)

        layout.addWidget(QLabel("Searches"))
        self.search_list = QListWidget()
        self.search_list.setWordWrap(True)
        self.search_list.itemActivated.connect(self.open_item)       # Enter
        self.search_list.itemDoubleClicked.connect(self.open_item)  # double-click
        layout.addWidget(self.search_list, 1)  # stretch factor 1

        layout.addWidget(QLabel("Visited pages"))
        self.page_list = QListWidget()
        self.page_list.setWordWrap(True)
        self.page_list.itemActivated.connect(self.open_item)
        self.page_list.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.page_list, 2)  # a bit taller than searches

        buttons = QHBoxLayout()  # row of buttons at the bottom
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.open_selected)
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self.clear_history)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)  # close without opening a URL
        buttons.addWidget(open_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch()  # push Close to the right
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.populate_lists()  # fill the lists when the window opens

    def populate_lists(self):
        # Rebuild both lists from history.json, newest first, using the filter text.
        needle = self.filter_bar.text().strip().lower()
        history = list(reversed(load_json_list(HISTORY_FILE)))

        self.search_list.clear()
        self.page_list.clear()
        seen_searches = set()  # show each search phrase only once

        for item in history:
            url = item.get("url", "")
            title = item.get("title") or url
            query = item.get("query") or search_query_from_url(url)
            visited_at = item.get("visited_at", "")
            kind = item.get("kind") or ("search" if query else "page")
            haystack = " ".join([title, url, query, visited_at]).lower()
            if needle and needle not in haystack:
                continue  # does not match the filter box

            if kind == "search" and query:
                key = query.lower()
                if key in seen_searches:
                    continue
                seen_searches.add(key)
                label = f"{query}\n{visited_at}  {url}".strip()
                self._add_item(self.search_list, label, url)
            else:
                label = f"{title}\n{visited_at}  {url}".strip()
                self._add_item(self.page_list, label, url)

        # Empty-state messages (not clickable).
        if self.search_list.count() == 0:
            placeholder = QListWidgetItem("No searches yet. Type a query in the address bar.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.search_list.addItem(placeholder)

        if self.page_list.count() == 0:
            placeholder = QListWidgetItem("No visited pages yet.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.page_list.addItem(placeholder)

    def _add_item(self, widget, label, url):
        # One visible row. The real URL is stored on the item, hidden from the label.
        row = QListWidgetItem(label)
        row.setData(Qt.UserRole, url)
        widget.addItem(row)

    def current_item(self):
        # Prefer a selected search, otherwise a selected page. Skip placeholders.
        for widget in (self.search_list, self.page_list):
            item = widget.currentItem()
            if item is not None and item.data(Qt.UserRole):
                return item
        return None

    def open_item(self, item):
        # Remember the URL and close the dialog with "Accepted".
        url = item.data(Qt.UserRole) if item is not None else ""
        if url:
            self.selected_url = url
            self.accept()

    def open_selected(self):
        # The Open button uses whichever row is currently selected.
        self.open_item(self.current_item())

    def clear_history(self):
        # Wipe history.json, then refresh the lists.
        save_json_list(HISTORY_FILE, [])
        self.populate_lists()


class BookmarksDialog(QDialog):
    """Popup that lists saved bookmarks."""

    def __init__(self, parent):
        super().__init__(parent)
        self.selected_url = ""
        self.setWindowTitle("Bookmarks")
        self.resize(720, 520)
        self.setStyleSheet(GALAXY_QSS)

        layout = QVBoxLayout(self)

        heading = QLabel("Bookmarks")
        heading.setStyleSheet("font-size: 22px; font-weight: 600; padding: 4px 0;")
        layout.addWidget(heading)

        hint = QLabel("Press ★ on a page to save it. Double-click a row to open it.")
        hint.setStyleSheet("color: #cbb8ff; padding-bottom: 4px;")
        layout.addWidget(hint)

        self.filter_bar = QLineEdit()
        self.filter_bar.setPlaceholderText("Filter bookmarks...")
        self.filter_bar.textChanged.connect(self.populate_list)
        layout.addWidget(self.filter_bar)

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.itemActivated.connect(self.open_item)
        self.list_widget.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.open_selected)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(open_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.populate_list()

    def populate_list(self):
        needle = self.filter_bar.text().strip().lower()
        bookmarks = list(reversed(load_json_list(BOOKMARKS_FILE)))

        self.list_widget.clear()
        for item in bookmarks:
            url = item.get("url", "")
            title = item.get("title") or url
            saved_at = item.get("saved_at", "")
            haystack = " ".join([title, url, saved_at]).lower()
            if needle and needle not in haystack:
                continue
            label = f"{title}\n{saved_at}  {url}".strip()
            row = QListWidgetItem(label)
            row.setData(Qt.UserRole, url)
            self.list_widget.addItem(row)

        if self.list_widget.count() == 0:
            placeholder = QListWidgetItem("No bookmarks yet. Open a page and press ★.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(placeholder)

    def current_item(self):
        item = self.list_widget.currentItem()
        if item is not None and item.data(Qt.UserRole):
            return item
        return None

    def open_item(self, item):
        url = item.data(Qt.UserRole) if item is not None else ""
        if url:
            self.selected_url = url
            self.accept()

    def open_selected(self):
        self.open_item(self.current_item())

    def remove_selected(self):
        item = self.current_item()
        if item is None:
            return
        url = item.data(Qt.UserRole)
        bookmarks = [row for row in load_json_list(BOOKMARKS_FILE) if row.get("url") != url]
        save_json_list(BOOKMARKS_FILE, bookmarks)
        self.populate_list()


# Qt Style Sheet (like CSS) for the window, tabs, address bar, and buttons.
GALAXY_QSS = """
QMainWindow, QWidget {
    background-color: #0b0720;      /* deep space */
    color: #e6dcff;
    font-family: 'Segoe UI', 'Noto Sans', 'Ubuntu', 'DejaVu Sans', sans-serif;
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

QStatusBar { background: #120a30; color: #cbb8ff; }

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


# This block runs only when you start the file with: python main.py
# (It does not run if another file imports this one.)
if __name__ == "__main__":
    # These attributes must be set before QApplication is created.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)  # needed by Qt WebEngine
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    app.setOrganizationName("Orion")
    app.setApplicationName("Orion Browser")
    configure_webengine()

    if not os.path.exists(HOME_HTML):
        QMessageBox.warning(
            None,
            "Orion Browser",
            "home.html was not found next to main.py.\nThe first tab may be blank.",
        )

    window = OrionBrowser()
    window.show()
    sys.exit(app.exec_())
