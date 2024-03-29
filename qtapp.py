# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 16:48:55 2017

@author: МакаровАС
"""

import platform
import subprocess
import py_compile
import sys
import traceback
import signal
from pathlib import Path
from types import SimpleNamespace
from qtpy import QtCore, QtGui, QtWidgets, uic
from qtpy import API as Qt_API, parse as ver, QT_VERSION
Qt = QtCore.Qt
_app = None  # QApplication instance
options = {'skip_missing_resources': False, 'debug': False,
           'slot_prefix': '', 'compiled_qrc': True}
# QWidget init `flags` argument
flags_kw_d = 'flags' if Qt_API.startswith('pyqt') else 'f'
flags_kws = {'PySide2.QtWidgets.QWizard': 'flags'}
if Qt_API.startswith('pyside'):
    import pyside2uic  # monkey-patch qtpy to use pyside2uic with PySide2
    uic.compileUi = pyside2uic.compileUi
backend_pkgs = Qt_API, "shiboken", "sip"  # Qt related lowercase package names

print("Qt %s, bindings %s" % (QT_VERSION, Qt_API))

try:  # Application path
    import __main__
    app_entry = Path(sys.executable if getattr(sys, 'frozen', False)
                     else __main__.__file__)
    app_path = app_entry.parent
except AttributeError:  # interactive interpreter mode
    import os
    app_path = Path(os.getcwd())
    app_entry = app_path / "<interpreter>"


def debug(*args, flush=True, **kwargs):
    if options.get('debug'):
        print(*args, **kwargs, flush=flush)


def is_Qt_class(cls, is_qwidget=None):
    """
    Checks if a class is from Qt/sip/Shiboken package
    is_qwidget=None|True - check additionally if the class is QWidget subclass
    """
    if not cls.__module__.split(".", 1)[0].lower() in backend_pkgs:
        return False
    if is_qwidget:
        return issubclass(cls, QtWidgets.QWidget)
    return True


def loadUiType(uifile):
    "loadUiType which also compiles and loads resources"
    from io import StringIO
    code_string = StringIO()
    uic.compileUi(uifile, code_string)
    winfo = parse_ui(uifile)  # get info from ui-file
    res_imports = ["import %s_rc" % i.stem for i in winfo['resources']]
    source = "\n".join(i for i in code_string.getvalue().splitlines()
                       if i not in res_imports)  # skip resource files
    ui_globals = {}
    exec(source, ui_globals)
    for i in winfo['resources']:
        load_qrc(i, Path(uifile).parent)
    return (ui_globals["Ui_" + winfo["uiclass"]],
            getattr(QtWidgets, winfo["baseclass"]))


def import_file(path):
    "Import module from any `path`, adds it to `sys.modules` as `MOD__(path)`"
    path = Path(path)
    try:  # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(path.stem, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules["MOD__%s" % path] = mod
    except AttributeError:  # fallback to Python 3.3 implementation
        if path.suffix.lower() == ".pyc":
            from importlib.machinery import SourcelessFileLoader as _loader
        else:
            from importlib.machinery import SourceFileLoader as _loader
        _loader("MOD__%s" % path, str(path)).load_module()


def parse_ui(uifile):
    "Extract base class, UI class and resource file paths from ui-file"
    import xml.etree.ElementTree as ET
    ret = {'baseclass': '', 'uiclass': '', 'resources': ()}
    root = ET.parse(uifile).getroot()
    widget = root.find('widget')
    if widget:
        ret['baseclass'] = widget.attrib['class']
        ret['uiclass'] = widget.attrib['name']
    resources = root.find('resources')
    if resources:
        ret['resources'] = [Path(i.attrib['location'])
                            for i in resources.findall('include')]
    return ret


def subprocess_run(args):
    "Runs a command, raises exception on error, returns nothing"
    if hasattr(subprocess, 'run'):  # py3.5+
        subprocess.run(args, check=True)
    else:
        rc = subprocess.call(args)
        if rc:
            raise subprocess.CalledProcessError(rc, args)


def rcc(qrc_path, output_path):
    "Compile resources"
    args = ['-o', str(output_path), str(qrc_path)]
    if ver(QT_VERSION) < ver("5"):
        # https://riverbankcomputing.com/pipermail/pyqt/2010-December/028669.html
        subprocess_run(['pyrcc4', '-py3'] + args)
    elif Qt_API.startswith('pyside'):
        subprocess_run(['pyside2-rcc'] + args)
    else:  # exe->bat https://www.riverbankcomputing.com/pipermail/pyqt/2017-January/038529.html
        try:
            subprocess_run(['pyrcc5'] + args)
        except FileNotFoundError:
            subprocess_run(['pyrcc5.bat'] + args)


def compile_qrc(path_qrc, path_dst: Path):
    "Compile .qrc file to .py then optionally to .pyc"
    target_path = path_dst.parent
    path_py = target_path / "_temp_rc_.py" \
        if path_dst.suffix.lower() == ".pyc" else path_dst
    rcc(path_qrc, path_py)
    if path_dst.suffix.lower() == ".pyc":  # compile to .pyc
        py_compile.compile(str(path_py), cfile=str(path_dst), doraise=True)
        path_py.unlink()
    debug("Resource file %s compiled" % path_qrc)


def load_qrc(path_qrc, target_path):
    "Compile resource file to `target_path` if needed and load it"
    target_path, path_qrc = Path(target_path), Path(path_qrc)
#    if not path_qrc.is_absolute():
#        path_qrc = target_path.joinpath(path_qrc)
    if not path_qrc.exists():
        if options.get('skip_missing_resources'):
            debug("Resource file not found:", path_qrc)
            return
        raise FileNotFoundError(path_qrc)
    ext = ".pyc" if options.get('compiled_qrc') else ".py"
    path_pyc = (target_path / ("rc_" + path_qrc.name)).with_suffix(ext)
    if not path_pyc.exists() or (path_pyc.stat().st_mtime <
                                 path_qrc.stat().st_mtime):
        compile_qrc(path_qrc, path_pyc)
    try:
        import_file(str(path_pyc))
    except ImportError:  # try to rebuild resource file
        print("Failed to load resource file %s. Rebuilding..." % path_pyc)
        compile_qrc(path_qrc, path_pyc)
        import_file(str(path_pyc))


def app():
    "QApplication instance"
    global _app
    if _app is None:
        _app = QtApp()
    return _app


def get_icon(icon):
    "icon - QIcon|QStyle.StandardPixmap|image-path"
    if isinstance(icon, QtGui.QIcon):
        return icon
    if isinstance(icon, QtWidgets.QStyle.StandardPixmap):
        icon_factory = QtWidgets.qApp.style().standardIcon
    elif isinstance(icon, str):
        icon_factory = QtGui.QIcon
        if not icon.startswith(":/"):  # resource
            path = Path(icon)
            if not path.is_absolute():
                icon = str(app_path.joinpath(icon))
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
        if QtWidgets.QApplication.startingUp():
            debug("Init QApplication instance")
        else:
            debug("Reusing existing QApplication instance")
        super().__init__(sys.argv)
        if ver(QT_VERSION) >= ver("5.5.1"):
            # http://stackoverflow.com/questions/33736819/pyqt-no-error-msg-traceback-on-exit
            def excepthook(type_, value, traceback_):
                traceback.print_exception(type_, value, traceback_)
                QtCore.qFatal('')
            sys.excepthook = excepthook
#        with contextlib.suppress(pywintypes.error):
#            win32gui.EnumWindows(self.findMsgDispatcher, self.applicationPid())

        # Pass all KeyboardInterrupt to Python code
        signal.signal(signal.SIGINT, self.on_sigint)
        # Notify about SIGINT even if application's window is not in focus
        # https://machinekoder.com/how-to-not-shoot-yourself-in-the-foot-using-python-qt/
        self.timer_eventloop = QtCore.QTimer()
        self.timer_eventloop.timeout.connect(lambda: None)
        self.timer_eventloop.start(100)

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

        # default window icon
        if platform.system() == "Windows":
            # https://stackoverflow.com/a/27872625/1119602
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                str(app_entry))
        self.setWindowIcon(get_icon(QtWidgets.QStyle.SP_TitleBarMenuButton))

    @classmethod
    def load_resources(path):
        "Load .qrc file from specified `path`"
        target_path = str(Path(path).parent.absolute())
        load_qrc(path, target_path)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent):
        event_type = event.type()
        if event_type == QtCore.QEvent.ApplicationDeactivate:
            self.deactivated.emit()
        elif event_type == QtCore.QEvent.Wheel:
            delta = event.angleDelta().y() if hasattr(event, 'angleDelta') \
                else event.delta()
            self.wheel.emit(obj, delta > 0)
        return False

    def on_sigint(self, *args):
        "Actions performed on SIGINT (Ctrl+C)"
        debug('SIGINT received')
        self.terminated.emit()
        self.quit()
        # raise KeyboardInterrupt

    def exec(self):
        "Start main event loop after QApplication initialization"
        try:
            # https://stackoverflow.com/a/22614643/1119602
            ret = super().exec_()  # there's no `exec` in PySide
            if ret == -1:
                debug('Application loop is already running')
                return
            sys.exit(ret)
        except SystemExit:
            debug('Exit main loop')


def mod_path(cls):
    "Get module folder path from class"
    return Path(sys.executable if getattr(sys, 'frozen', False) else
                sys.modules[cls.__module__].__file__).absolute().parent


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def addMenuItem(self, *args):
        for i in range(0, len(args), 2):
            self.contextMenu().addAction(args[i]).triggered.connect(args[i+1])


def split_kwargs(kwargs):
    "Split dict into 2 dicts by `_super` postfix in keys"
    kw, super_kw = {}, {}
    for k, v in kwargs.items():
        if k.endswith("_super"):
            super_kw[k[:-6]] = v
        else:
            kw[k] = v
    return kw, super_kw


def generate_widget_class(Cls, Ui_Cls, init_args, Base_Cls=QtWidgets.QWidget):
    """
    Generates a class based on `Cls`, `QtFormWrapper` and `QWidget` if needed
    `Ui_Cls` - None or tuple of classes returned by `loadUiType`
    `init_args` - `SimpleNamespace` arguments object. It is set as a variable
                  of the generated class
    `Base_Cls`=QWidget - base Qt widget class, it should derive from QWidget
    """
    bases = QtFormWrapper, Cls
    if Ui_Cls:
        bases += Ui_Cls
    assert issubclass(Base_Cls, QtWidgets.QWidget), \
        "Base_Cls does not derive from QWidget"
    if not (Ui_Cls or issubclass(Cls, Base_Cls)):
        bases += Base_Cls,
    Generated_Cls = type("%s__Wrapper" % Cls.__name__, bases, {})
    Generated_Cls.init_args = init_args
    return Generated_Cls


def first_val(*args):
    "Returns first not None value or None"
    return next((item for item in args if item is not None), None)


def show_splashscreen(splash):
    splash_image = QtGui.QPixmap(splash['image'])
    w, h = splash.get('width'), splash.get('height')
    if w and not h:
        h = splash_image.height() * (w / splash_image.width())
    elif h and not w:
        w = splash_image.width() * (h / splash_image.height())
    if w and h:
        splash_image = splash_image.scaled(w, h)
    sp_scr = QtWidgets.QSplashScreen(splash_image, Qt.WindowStaysOnTopHint)
    sp_scr.show()
    if splash.get('title'):  # Show message
        sp_scr.showMessage(splash['title'],
                           splash.get('align',
                                      Qt.AlignHCenter | Qt.AlignBottom),
                           splash.get('color', Qt.black))
    return sp_scr


def QTBUG_50271(widget):
    # Sync actual behaviour with WindowStaysOnTopHint flag
    # https://bugreports.qt.io/browse/QTBUG-50271
    # https://stackoverflow.com/questions/51802118
    if not (platform.system() == "Windows" and ver(QT_VERSION) < ver("5.10.1")):
        return
    import ctypes
    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 8
    HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
    SWP_NOSIZE, SWP_NOMOVE = 1, 2
    is_topmost = user32.GetWindowLongW(int(widget.winId()), GWL_EXSTYLE) \
        & WS_EX_TOPMOST == WS_EX_TOPMOST
    b = widget.windowFlags() & Qt.WindowStaysOnTopHint == \
        Qt.WindowStaysOnTopHint
    if b != is_topmost:
        debug("Fix: Make window topmost")
        flag = HWND_TOPMOST if b else HWND_NOTOPMOST
        swp = lambda: user32.SetWindowPos(int(widget.winId()), flag, 0, 0, 0,
                                          0, SWP_NOSIZE | SWP_NOMOVE)
        QtCore.QTimer.singleShot(0, swp)  # call later


def QtForm(Form, *args, flags=None, ui=None, ontop=None, show=None, icon=None,
           tray=None, splash=None, loop=None, connect=None, slot_prefix=None,
           title=None, layout=None, draggable=None, _base=QtWidgets.QWidget,
           **kwargs):
    # get arguments from class members: _ArgName_
    getatt = lambda name: getattr(Form, name, None)
    opt = SimpleNamespace(
        flags=first_val(flags, getatt("_flags_")),
        ui=first_val(ui, getatt("_ui_")),
        ontop=first_val(ontop, getatt("_ontop_"), False),
        show=first_val(show, getatt("_show_"), True),
        icon=first_val(icon, getatt("_icon_")),
        tray=first_val(tray, getatt("_tray_")),
        splash=first_val(splash, getatt("_splash_"), {}),
        loop=first_val(loop, getatt("_loop_"), False),
        connect=first_val(connect, getatt("_connect_"), 'after'),
        slot_prefix=first_val(slot_prefix, getatt("_slot_prefix_")),
        title=first_val(title, getatt("_title_")),
        layout=first_val(layout, getatt("_layout_")),
        draggable=first_val(draggable, getatt("_draggable_")),
        UserClass=Form,
    )
    # Note: do not store widget ref. in QtApp instance or del. it before exit
    app()  # Init QApplication if needed

    if opt.splash:  # Show splashscreen
        if isinstance(opt.splash, (str, Path)):
            opt.splash = {'image': opt.splash}
        opt.splash['sp_scr'] = show_splashscreen(opt.splash)
    uic_cls = ()
    if opt.ui != False:  # loading .ui is not disabled
        ui_path = str(opt.ui or mod_path(Form).joinpath(Form.__name__.lower()))
        if not ui_path.lower().endswith(".ui"):
            ui_path += ".ui"
        if Path(ui_path).exists():
            uic_cls = loadUiType(ui_path)
        else:
            debug("Cannot load UI file", ui_path)
    Widget_cls = generate_widget_class(Form, uic_cls, opt, _base)
    instance = Widget_cls(*args, **kwargs)
    if opt.show:
        instance.show()
    if opt.splash:
        opt.splash['sp_scr'].close()  # finish(instance)
    if opt.loop:
        app().exec()
    return instance


def Dialog(Form, *args, get_result=True, **kwargs):
    """
    Constructs and shows a modal dialog.
    QDialog's `accept` can be called with an answer argument.
    Dialog instance has `answer` function to get user answer.
    If `get_result`=True returns `(result, answer)` otherwise QDialog instance
    """
    # WARNING: Do not add unbound methods which refer to `instance`.
    # It prevents object from being collected by gc. Use `types.MethodType` or
    # inheritance (see `Dialog_`).
    assert 'show' not in kwargs, "Dialog does not support `show` argument"
    assert '_base' not in kwargs, "Dialog does not support `_base` argument"
    class Dialog_(QtWidgets.QDialog):
        _answer = None

        def accept(self, retval=None):
            self._answer = retval
            super().accept()

        def reject(self, retval=None):
            self._answer = retval
            super().reject()

        def answer(self):
            return self._answer
    instance = QtForm(Form, *args, show=False, _base=Dialog_, **kwargs)
    # instance.setAttribute(Qt.WA_DeleteOnClose, True)
    instance.exec()
    if get_result:
        return instance.result(), instance._answer
    return instance


class QtFormWrapper():
    init_args = None  # generate_widget_class sets to `SimpleNamespace` object

    def __init__(self, *args, **kwargs):
        # Find base Qt class, check that the class derives from QWidget
        BaseWidget = next(i for i in self.__class__.__mro__
                          if is_Qt_class(i, is_qwidget=True))
        base_cls_name = "%s.%s" % (BaseWidget.__module__, BaseWidget.__name__)
        opt = self.init_args
        flags_ = (Qt.WindowFlags(opt.flags or 0) |
                  (Qt.WindowStaysOnTopHint if opt.ontop else 0))
        kwargs, super_kwargs = split_kwargs(kwargs)
        if flags_:
            flags_kw = flags_kws.get(base_cls_name, flags_kw_d)
            super_kwargs[flags_kw] = Qt.WindowFlags(flags_)
            # Alternatively __init__ exception text can be parsed:
            # PySide: "'f()' is not a Qt property or a signal"
            # PyQt: "'f' is an unknown keyword argument"
            # str(e).split(maxsplit=1)[0].strip('\'"()')
        BaseWidget.__init__(self, **super_kwargs)
        if hasattr(self, "setupUi"):  # init `loadUiType` generated class
            self.setupUi(self)
            if self.layout() and opt.layout:
                raise Exception("Widget already has layout from UI file")
        if opt.layout and issubclass(opt.layout, QtWidgets.QLayout):
            opt.layout(self)
        if opt.icon:
            self.setWindowIcon(get_icon(opt.icon))
        if opt.title:
            self.setWindowTitle(opt.title)
        if opt.tray is not None:
            self.init_tray({} if opt.tray is True else opt.tray)
        self.app = app()
        self.splashscreen = opt.splash.get('sp_scr', None)
        self.generateElipsisMenus()
        self.set_slot_prefix(opt.slot_prefix or options.get("slot_prefix"))
        self._connections = []  # list of connections made by `connect_all`
        self.__connect_called = False
        if opt.connect == 'before':
            self.connect_all()  # connect signals and events
        if "__init__" in opt.UserClass.__dict__:
            opt.UserClass.__init__(self, *args, **kwargs)
        self.splashscreen = None  # delete splash screen
        if opt.connect == 'after' and not self.__connect_called:
            self.connect_all()  # connect signals and events
        if opt.draggable:
            self._dragging_start_pos = None
            self.mousePressEvent = self._mousePressEvent
            self.mouseMoveEvent = self._mouseMoveEvent
            self.mouseReleaseEvent = self._mouseReleaseEvent
        QTBUG_50271(self)  # topmost

    def _mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging_start_pos = event.pos()
        super().mousePressEvent(event)

    def _mouseMoveEvent(self, event):
        if self._dragging_start_pos:
            # https://doc.qt.io/qt-5/application-windows.html#window-geometry
            frame_shift = self.geometry().topLeft() - self.pos()
            new_pos = event.pos() - self._dragging_start_pos - frame_shift
            self.move(self.mapToParent(new_pos))
        super().mouseMoveEvent(event)

    def _mouseReleaseEvent(self, event):
        self._dragging_start_pos = None
        super().mouseReleaseEvent(event)

    def init_tray(self, tray_opts={}):
        # Tray icon parent is VERY important:
        # http://python.6.x6.nabble.com/QSystemTrayIcon-still-crashed-app-PyQt4-4-9-1-td4976041.html
        if hasattr(self, "tray"):
            raise Exception("Widget already has 'tray' attr")
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

    def set_slot_prefix(self, prefix):
        if not prefix:
            self.slot_prefix = ""
            return
        if not prefix.isidentifier():
            raise Exception("Provided prefix '%s' is not a valid "
                            "Python identifier" % prefix)
        self.slot_prefix = prefix + "_"  # prefix always ends with underscore

    def connect_all(self):
        """Connect signals and events to appropriate members.
        Installs event filter if there's /eventFilter/ member.
        Example: def <object>_<signal/slot>():"""
        self.__connect_called = True
        if self._connections:
            debug("Reconnect all")
            for meth, handl in self._connections:
                meth.disconnect(getattr(self, handl))
            self._connections = []
        widgets = super().__dict__.copy()
        widgets['self'] = self
        members = {}  # all user class attributes
        for i in self.init_args.UserClass.__mro__[:-1]:  # except for `object`
            if not is_Qt_class(i):  # skip Qt/sip/Shiboken classes
                members.update(i.__dict__)
        con_sig, con_evt = [], []
        for i in widgets:
            if not hasattr(widgets[i], 'metaObject') or \
                    callable(widgets[i]):  # FIXME: why callables(?)
                continue  # FIXME: redirect stdout closeEvent(?)
            signals = _get_object_methods(widgets[i],
                                            QtCore.QMetaMethod.Signal)
#                print(i, signals)
            for m in members:
                if not m.startswith(self.slot_prefix + i + "_"):
                    continue
                meth_name = m[len(self.slot_prefix) + len(i) + 1:]
                method = getattr(widgets[i], meth_name, None)
                if not method:
                    print("Method '%s' of '%s' not found" % (meth_name, i))
                    continue
                binded_method = getattr(self, m)  # resolves inherit. problem
                if meth_name in signals:
                    method.connect(binded_method)
                    # save names instead of refs or will crash on app.quit
                    self._connections.append((method, m))
                    con_sig.append("%s.%s" % (i, meth_name))
                else:  # assume it's an event  # elif i != 'self'
                    setattr(widgets[i], meth_name, binded_method)
                    con_evt.append("%s.%s" % (i, meth_name))
        if "eventFilter" in members:
            self.installEventFilter(self)
            con_evt.append("Event filter")
        if con_sig:
            debug("Signals connected:", ", ".join(con_sig))
        if con_evt:
            debug("Events connected:", ", ".join(con_evt))

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

    def setTopmost(self, b=True):
        was_visible = self.isVisible()
        if was_visible:
            # `setWindowFlags` resets size if setGeometry was never called
            self.setGeometry(self.geometry())
        try:  # Qt>=5.9
            self.setWindowFlag(Qt.WindowStaysOnTopHint, b)
        except AttributeError:
            flags = self.windowFlags()
            self.setWindowFlags((flags | Qt.WindowStaysOnTopHint)
                                if b else
                                (flags & ~Qt.WindowStaysOnTopHint))
        if was_visible:
            self.show()
        QTBUG_50271(self)  # topmost

    def isTopmost(self):
        return self.windowFlags() & Qt.WindowStaysOnTopHint == \
            Qt.WindowStaysOnTopHint


if __name__ == '__main__':
    class ParentClass():
        def __init__(self):
            self.pushButton2 = QtWidgets.QPushButton("Push 2", self)
            self.layout().addWidget(self.pushButton2)

        def pushButton2_clicked(self):
            print('Button 2 clicked')

    class Form(ParentClass):
        _loop_ = True
        _layout_ = QtWidgets.QVBoxLayout
        _ontop_ = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.pushButton1 = QtWidgets.QPushButton("Push 1", self)
            self.layout().addWidget(self.pushButton1)
            self.setGeometry(200, 200, 200, 200)

        def pushButton1_clicked(self):
            print('Button 1 clicked')

        def paintEvent(self, event):
            p = QtGui.QPainter(self)
            t = "Center of the widget"
            p.setPen(QtGui.QColor("white"))
            p.drawText(event.rect().translated(1, 1), Qt.AlignCenter, t)
            p.setPen(QtGui.QColor("gray"))
            p.drawText(event.rect(), Qt.AlignCenter, t)

    options['debug'] = True
    QtForm(Form)
