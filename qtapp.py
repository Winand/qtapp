# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 16:48:55 2017

@author: МакаровАС
"""

import subprocess
import py_compile
import sys
import traceback
import signal
from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets  # , uic
from PyQt5 import uic  # FIXME: using PyQt5 and qtpy.)
_app = None  # QApplication instance
_forms = []


try:  # Application path
    import __main__
    app_path = Path(sys.executable if getattr(sys, 'frozen', False)
                    else __main__.__file__).parent
except AttributeError:  # interactive interpreter mode
    import os
    app_path = Path(os.getcwd())


def loadUiType(uifile):
    "loadUiType which also compiles and loads resources"
    from io import StringIO
    code_string = StringIO()
    winfo = uic.compiler.UICompiler().compileUi(uifile, code_string, False, '',
                                                '.')
    res_files = list_qrc(uifile)
    res_imports = ["import " + i.stem for i in res_files]
    source = "\n".join(i for i in code_string.getvalue().splitlines()
                       if i not in res_imports)  # skip resource files
    ui_globals = {}
    exec(source, ui_globals)
    for i in list_qrc(uifile):
        load_qrc(i, Path(uifile).parent)
    return (ui_globals[winfo["uiclass"]],
            getattr(QtWidgets, winfo["baseclass"]))


def import_file(path):
    "Import module from `path`"
    path = Path(path)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except:
        from importlib.machinery import SourceFileLoader
        SourceFileLoader(path.stem, str(path)).load_module()
        

def list_qrc(uifile):
    "Search ui-file for resource file paths"
    import xml.etree.ElementTree as ET
    resources = ET.parse(uifile).getroot().find('resources')
    if resources:
        return [Path(i.attrib['location'])
                for i in resources.findall('include')]
    return ()

def load_qrc(res_file, target_path):
    "Compile resource file to `target_path` and load it"
    target_path, path_qrc = Path(target_path), Path(res_file)
    if not path_qrc.is_absolute():
        path_qrc = target_path.joinpath(path_qrc)
    if not path_qrc.exists():
        raise FileNotFoundError(res_file)
    path_pyc = (target_path / ("_" + path_qrc.name)).with_suffix(".pyc")
    if not path_pyc.exists() or (path_pyc.stat().st_mtime < \
                                 path_qrc.stat().st_mtime):
        path_py = target_path / "_temp_rc_.py"
        if subprocess.call(['pyrcc5', '-o', str(path_py), str(path_qrc)]):
            raise Exception("Failed to compile resource file " + str(path_qrc))
        py_compile.compile(str(path_py), cfile=str(path_pyc), doraise=True)
        path_py.unlink()
    import_file(str(path_pyc))
        

def app():
    if _app is None:
        print("app: Call QtApp or QtForm first")
    return _app


def exec_():
    "Start main event loop after QApplication initialization"
#    del app().form  # ...or you WILL fail. One day.
    try:
        sys.exit(app().exec_())
    except SystemExit:
        print('Exit main loop')
        pass


def get_icon(icon):
    "icon - QIcon|QStyle.StandardPixmap|image-path"
    if isinstance(icon, QtGui.QIcon):
        return icon
    if isinstance(icon, QtWidgets.QStyle.StandardPixmap):
        icon_factory = QtWidgets.qApp.style().standardIcon
    elif isinstance(icon, str):
        icon_factory = QtGui.QIcon
        path = Path(icon)
        if not path.is_absolute():
            icon = str(Path.app_path.joinpath(icon))
    else:
        return
    return icon_factory(icon)


def _get_object_methods(obj, method_type):
    "Get all members of `obj` of type `method_type` (QtCore.QMetaMethod)"
    mo, methods = obj.metaObject(), []
    for j in range(0, mo.methodCount()):
        method = mo.method(j)
        if method.methodType() == method_type:
            if hasattr(method, 'name'):
                methods.append(str(method.name(), encoding='ascii'))
            else:  # Qt4
                signature = method.signature()
                methods.append(signature[:signature.index("(")])
    return methods


class QtApp(QtWidgets.QApplication):
    (terminated,  # emitted if WM_DESTROY is sent to GUI thread dispatcher's
                  # (see also QProcess.terminate)
     deactivated,  # emitted when application loses focus
     ) = (QtCore.Signal() for i in range(2))
    # emitted when mouse wheel rolled above /object/
    wheel = QtCore.Signal(object, bool)

#    class NativeEventFilter(QtCore.QAbstractNativeEventFilter):
#        def __init__(self, obj):
#            super().__init__()
#            self.obj = obj
#            obj.installNativeEventFilter(self)
#
#        def nativeEventFilter(self, eventType, message):
#            message = ctypes.wintypes.MSG.from_address(message.__int__())
#            print(eventType, message.message)
#            return self.obj.winEventFilter(message)

    def __init__(self):
        print("Init QApplication instance")
        super().__init__(sys.argv)
        if QtCore.QT_VERSION >= 0x50501:
            # http://stackoverflow.com/questions/33736819/pyqt-no-error-msg-traceback-on-exit
            def excepthook(type_, value, traceback_):
                traceback.print_exception(type_, value, traceback_)
                QtCore.qFatal('')
            sys.excepthook = excepthook
#        with contextlib.suppress(pywintypes.error):
#            win32gui.EnumWindows(self.findMsgDispatcher, self.applicationPid())

        def sigint(*args):  # pass all KeyboardInterrupt to Python code
            self.terminated.emit()
            self.quit()
#            raise KeyboardInterrupt
        signal.signal(signal.SIGINT, sigint)
        global _app
        _app = self
        self.path = app_path  # Application path
        self.installEventFilter(self)
#        self.native_event_filter = self.NativeEventFilter(self)

#    def findMsgDispatcher(self, hwnd, lParam):
#        if lParam == win32process.GetWindowThreadProcessId(hwnd)[1]:
#            if win32gui.GetClassName(hwnd) \
#                        .startswith("QEventDispatcherWin32_Internal_Widget"):
#                self.msg_dispatcher = hwnd
#                return False
#
#    def winEventFilter(self, message):
##        print('winEventFilter', message.message, message.hwnd if hasattr(message, 'hwnd') else "")
#        if message.message == win32con.WM_DESTROY:
#            # GUI thread dispatcher's been killed
#            if int(message.hwnd) == self.msg_dispatcher:
#                self.terminated.emit()
#                self.quit()
#        return False, 0

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent):
        event_type = event.type()
        if event_type == QtCore.QEvent.ApplicationDeactivate:
            self.deactivated.emit()
        elif event_type == QtCore.QEvent.Wheel:
            delta = event.angleDelta().y() if hasattr(event, 'angleDelta') \
                else event.delta()
            self.wheel.emit(obj, delta > 0)
        return False


def module_path(cls):
    "Get module folder path from class"
    return Path(sys.executable if getattr(sys, 'frozen', False) else
                sys.modules[cls.__module__].__file__).absolute().parent


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def addMenuItem(self, *args):
        for i in range(0, len(args), 2):
            self.contextMenu().addAction(args[i]).triggered.connect(args[i+1])


def QtForm(Form, *args, flags=QtCore.Qt.WindowType(), ui=None, ontop=False,
           show=True, icon=None, tray=None, splash=None, loop=False, **kwargs):
    global _app
    if QtWidgets.QApplication.startingUp():
        _app = QtApp()
    elif not _app:
        print("Reuse existing QApplication.instance()")
        _app = QtWidgets.QApplication.instance()
    # get arguments from class members: _ArgName_
    flags = getattr(Form, "_flags_", flags)
    ui = getattr(Form, "_ui_", ui)
    ontop = getattr(Form, "_ontop_", ontop)
    show = getattr(Form, "_show_", show)
    icon = getattr(Form, "_icon_", icon)
    tray = getattr(Form, "_tray_", tray)
    splash = getattr(Form, "_splash_", splash)
    loop = getattr(Form, "_loop_", loop)

    splash = {'image': splash} if isinstance(splash,
                                             (str, Path)) else splash
    if splash:
        sp_scr = QtWidgets.QSplashScreen(
            QtGui.QPixmap(app_path+splash['image']))  # FIXME: relative path?
        sp_scr.show()
        if splash.get('title'):  # Show message
            sp_scr.showMessage(splash['title'],
                               splash.get('align', QtCore.Qt.AlignHCenter |
                                                   QtCore.Qt.AlignBottom),
                               splash.get('color', QtCore.Qt.black))
    ui_path = str(ui or module_path(Form).joinpath(Form.__name__.lower())
                  ) + ".ui"
    uic_cls = ()
    if Path(ui_path).exists():
        uic_cls = tuple(reversed(loadUiType(ui_path)))
    else:
        print("Cannot load UI file", ui_path)

    class QtFormWrapper(Form, *uic_cls):
        def __init__(self, *args, **kwargs):
            fl = QtCore.Qt.WindowFlags(flags)
            if ontop:
                fl |= QtCore.Qt.WindowStaysOnTopHint
            super(Form, self).__init__(*args, flags=fl, **kwargs)
            if hasattr(self, "setupUi"):  # init `loadUiType` generated class
                self.setupUi(self)
            if icon or self.windowIcon().isNull():
                self.setWindowIcon(
                    get_icon(icon or QtWidgets.QStyle.SP_TitleBarMenuButton))
            if hasattr(self, "tray"):
                raise(Exception("Widget already has 'tray' attr"))
            self.init_tray({} if tray is True else tray)
            self.app = app()
            self.splashscreen = sp_scr if splash else None
            self.generateElipsisMenus()
            self._connections = []  # list of connections made by `connect_all`
            if uic_cls:  # if UI-file loaded
                self.connect_all()  # connect signals and events
            if "__init__" in Form.__dict__:
                Form.__init__(self, *args, **kwargs)
            self.splashscreen = None  # delete splash screen

        def init_tray(self, tray_opts={}):
            # Tray icon parent is VERY important:
            # http://python.6.x6.nabble.com/QSystemTrayIcon-still-crashed-app-PyQt4-4-9-1-td4976041.html
            if not (tray_opts or isinstance(tray_opts, dict)):
                self.tray = None  # no tray icon
                return
            if 'icon' not in tray_opts:  # get from window
                tray_opts["icon"] = self.windowIcon()
            self.tray = SystemTrayIcon(get_icon(tray_opts["icon"]), self)
            if 'tip' in tray_opts:
                self.tray.setToolTip(tray_opts['tip'])
            # Qt doc:"The system tray icon does not take ownership of the menu"
            self.tray.setContextMenu(QtWidgets.QMenu(self))
            self.tray.show()
            # important! open qdialog, hide main window, close qdialog:
            # trayicon stops working
    #        QtGui.qApp.setQuitOnLastWindowClosed(False)

        def connect_all(self):
            """Connect signals and events to appropriate members.
            Installs event filter if there's /eventFilter/ member.
            Example: def <object>_<signal/slot>():"""
            if self._connections:
                print("Reconnect all")
                for meth, handl in self._connections:
                    meth.disconnect(getattr(self, handl))
                self._connections = []
            widgets, members = super().__dict__.copy(), Form.__dict__
            widgets['self'] = self
#            print(widgets)
            con_sig, con_evt = [], []
            for i in widgets:
                if not hasattr(widgets[i], 'metaObject') or \
                        callable(widgets[i]):  # FIXME: why callables(?)
                    continue  # FIXME: redirect stdout closeEvent(?)
                signals = _get_object_methods(widgets[i],
                                              QtCore.QMetaMethod.Signal)
#                print(i, signals)
                for m in [j for j in members if j.startswith(i + "_")]:
                    meth_name = m[len(i)+1:]
                    method = getattr(widgets[i], meth_name, None)
                    if not method:
                        print("Method '%s' of '%s' not found" % (meth_name, i))
                        continue
                    binded_method = getattr(self, m)
                    if meth_name in signals:
                        method.connect(binded_method)
                        # save names instead of refs or will crash on app.quit
                        self._connections.append((method, m))
                        con_sig.append("%s.%s" % (i, meth_name))
                    elif i != 'self':  # assume it's an event
                        setattr(widgets[i], meth_name, binded_method)
                        con_evt.append("%s.%s" % (i, meth_name))
            if "eventFilter" in members:
                self.installEventFilter(self)
                con_evt.append("Event filter")
            if con_sig:
                print("Signals connected:", ", ".join(con_sig))
            if con_evt:
                print("Events connected:", ", ".join(con_evt))

        def generateElipsisMenus(self):
            "Group widgets in 'elipsis_...' layout under ⁞-button menu"
            widgets, elipsis_btns = super().__dict__, []
            for i in widgets:
                if i.startswith('elipsis_'):
                    elipsis = widgets[i]
                    if not isinstance(elipsis, QtWidgets.QLayout):
                        continue
                    menu = QtWidgets.QMenu()
                    wgts = [elipsis.itemAt(j).widget()
                            for j in range(elipsis.count())]
                    for wgt in wgts:
                        act_wgt = QtWidgets.QWidgetAction(menu)
                        act_wgt.setDefaultWidget(wgt)
                        menu.addAction(act_wgt)
                    elipsis_btn = QtWidgets.QToolButton(self)
                    elipsis_btn.setAutoRaise(True)
                    elipsis_btn.setStyleSheet(
                        "QToolButton:menu-indicator{image:none}")
                    elipsis_btn.setText("⁞")  # ⋮
                    elipsis_btn.setFont(QtGui.QFont('Arial Unicode MS', 9))
                    elipsis_btn.setPopupMode(elipsis_btn.InstantPopup)
                    elipsis.addWidget(elipsis_btn)
                    elipsis_btn.setMenu(menu)
                    elipsis_btn.setObjectName('elipsisbtn_'+i[8:])
                    elipsis_btns.append(elipsis_btn)
            for i in elipsis_btns:
                setattr(self, i.objectName(), i)

    instance = QtFormWrapper(*args, **kwargs)
    if show or splash:
        instance.show()
    if splash:
        sp_scr.close()  # finish(instance)
    if loop:
        exec_()
    return instance


if __name__ == '__main__':
    class Form(QtWidgets.QWidget):
        _loop_ = True
        _ontop_ = True

        def __init__(self, *args, **kwargs):
            self.ev_count = 0
            self.pushButton1 = QtWidgets.QPushButton(self)
            self.connect_all()

        def paintEvent(self, event):
            p = QtGui.QPainter(self)
            p.setPen(QtGui.QColor("gray"))
            p.drawText(event.rect(), QtCore.Qt.AlignCenter,
                       "Center of the widget")

    QtForm(Form)
else:
    print("Loaded shared qtapp module (Qt %s)" % QtCore.__version__)


# Documentation:
# `exec_()` - start main event loop
# `QtApp` - QApplication subclass
#   Members:
#   `path` - application path
# `app()` - `QtApp` instance
# `QtForm()` - create new Qt window. Arguments can be provided in variables
#              of user class: _argname_ = value
#   Arguments:
#   `Form` - user class to use as a subclass of `QWidget` (explicitly specify
#           super class [QDialog|QWidget|QMainWindow] if ui-file is not used)
#   `flags`=QtCore.Qt.WindowType() - Qt.WindowFlags
#   `ui`=None - path to .ui-file, if `None` try lowercase name of `Form` class
#   `ontop`=False - show window always on top
#   `icon`=None - set window icon: QIcon|QStyle.StandardPixmap|image-path
#   `show`=True - show window by default. Always True if `splash` provided.
#   `tray`=None - add tray icon: True (use QtForm window icon)|dict
#       Arguments:
#       {`tip` - tray icon tooltip,
#        `icon` - custom icon (see `QtForm` `icon` arg)}
#   `splash`=None - show splash screen: str|pathlib.Path|dict
#                   Pass image path only or options dict.
#       Arguments:
#       {`image` - path to splash screen image file,
#        `title`="Loading application..." - caption on the splash screen,
#        `align`=Qt.AlignHCenter|Qt.AlignBottom - caption alignment,
#        `color`=Qt.black - caption color}
#   `loop`=False - do not return and start main event loop
#   Members:
#   `app` - `QtApp` instance
#   `tray` - `QSystemTrayIcon` if created or None
#       Members:
#       `addMenuItem(name1, func1, ...)` - add 1 or more context menu items
#   `connect_all()` - connects events and signals to appropriate members:
#                    def ObjName_SignalName(...), special: def eventFilter(...)
#                    Note: It is called automatically if .ui-file is loaded
#                    Note: Use `self` as `ObjName` of `QtForm` signal handlers
#   `init_tray()` - init. tray icon manually, see `tray` arg. of `QtForm`
#   `splashscreen` - `QSplashScreen` if created or None. After _init_ it's None
