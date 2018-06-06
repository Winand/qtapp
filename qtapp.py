# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 16:48:55 2017

@author: МакаровАС
"""

import re
import subprocess
import py_compile
import sys
import traceback
import signal
from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets, uic
Qt = QtCore.Qt
_app = None  # QApplication instance
options = {'skip_missing_resources': False, 'debug': False,
           'slotconvention': "{object}_{signal}"}


try:  # Application path
    import __main__
    app_path = Path(sys.executable if getattr(sys, 'frozen', False)
                    else __main__.__file__).parent
except AttributeError:  # interactive interpreter mode
    import os
    app_path = Path(os.getcwd())


def debug(*args, flush=True, **kwargs):
    if options.get('debug'):
        print(*args, **kwargs, flush=flush)


def loadUiType(uifile):
    "loadUiType which also compiles and loads resources"
    from io import StringIO
    code_string = StringIO()
    uic.compileUi(uifile, code_string, resource_suffix='')
    winfo = parse_ui(uifile)  # get info from ui-file
    res_imports = ["import " + i.stem for i in winfo['resources']]
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


def compile_qrc(path_qrc, path_dst: Path):
    "Compile .qrc file to .py then optionally to .pyc"
    target_path = path_dst.parent
    path_py = target_path / "_temp_rc_.py" \
        if path_dst.suffix.lower() == ".pyc" else path_dst
    if subprocess.call(['pyrcc5', '-o', str(path_py), str(path_qrc)]):
        raise Exception("Failed to compile resource file " + str(path_qrc))
    if path_dst.suffix.lower() == ".pyc":  # compile to .pyc
        py_compile.compile(str(path_py), cfile=str(path_dst), doraise=True)
        path_py.unlink()


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
    path_pyc = (target_path / ("rc_" + path_qrc.name)).with_suffix(".pyc")
    if not path_pyc.exists() or (path_pyc.stat().st_mtime <
                                 path_qrc.stat().st_mtime):
        compile_qrc(path_qrc, path_pyc)
    try:
        import_file(str(path_pyc))
    except ImportError:  # try to rebuild resource file
        print("Failed to load resource file. Rebuilding...")
        compile_qrc(path_qrc, path_pyc)
        import_file(str(path_pyc))


def app():
    "QApplication instance"
    global _app
    if _app is None:
        _app = QtApp()
    return _app


def exec_():
    "Start main event loop after QApplication initialization"
#    del app().form  # ...or you WILL fail. One day.
    try:
        sys.exit(app().exec_())
    except SystemExit:
        debug('Exit main loop')


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

        # default window icon
        self.setWindowIcon(get_icon(QtWidgets.QStyle.SP_TitleBarMenuButton))

    def load_resources(self, path):
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


def module_path(cls):
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


def QtForm(Form, *args, flags=None, ui=None, ontop=False, show=True, icon=None,
           tray=None, splash=None, loop=False, connect='after',
           slotconvention=None, **kwargs):
    # get arguments from class members: _ArgName_
    flags = getattr(Form, "_flags_", flags)
    ui = getattr(Form, "_ui_", ui)
    ontop = getattr(Form, "_ontop_", ontop)
    show = getattr(Form, "_show_", show)
    icon = getattr(Form, "_icon_", icon)
    tray = getattr(Form, "_tray_", tray)
    splash = getattr(Form, "_splash_", splash)
    loop = getattr(Form, "_loop_", loop)
    connect = getattr(Form, "_connect_", connect)
    slotconvention = getattr(Form, "_slotconvention_", slotconvention)

    app()  # Init QApplication if needed

    splash = {'image': splash} if isinstance(splash,
                                             (str, Path)) else splash
    if splash:
        splash_image = QtGui.QPixmap(splash['image'])
        w, h = splash.get('width'), splash.get('height')
        if w and not h:
            h = splash_image.height() * (w / splash_image.width())
        elif h and not w:
            w = splash_image.width() * (h / splash_image.height())
        if w and h:
            splash_image = splash_image.scaled(w, h)
        sp_scr = QtWidgets.QSplashScreen(splash_image,
                                         Qt.WindowStaysOnTopHint)
        sp_scr.show()
        if splash.get('title'):  # Show message
            sp_scr.showMessage(splash['title'],
                               splash.get('align', Qt.AlignHCenter |
                                                   Qt.AlignBottom),
                               splash.get('color', Qt.black))
    ui_path = str(ui or module_path(Form).joinpath(Form.__name__.lower())
                  ) + ".ui"
    uic_cls = ()
    if Path(ui_path).exists():
        uic_cls = loadUiType(ui_path)
    else:
        debug("Cannot load UI file", ui_path)

    class QtFormWrapper(Form, *uic_cls):
        def __init__(self, *args, **kwargs):
            flags_ = (Qt.WindowFlags(flags or 0) |
                      (Qt.WindowStaysOnTopHint if ontop else 0))
            kwargs, super_kwargs = split_kwargs(kwargs)
            if flags_:
                super_kwargs['flags'] = Qt.WindowFlags(flags_)
            super(Form, self).__init__(**super_kwargs)
            if hasattr(self, "setupUi"):  # init `loadUiType` generated class
                self.setupUi(self)
            if icon:
                self.setWindowIcon(get_icon(icon))
            if hasattr(self, "tray"):
                raise(Exception("Widget already has 'tray' attr"))
            self.init_tray({} if tray is True else tray)
            self.app = app()
            self.splashscreen = sp_scr if splash else None
            self.generateElipsisMenus()
            self.set_slotname_convention(slotconvention or
                                         options.get("slotconvention"))
            self._connections = []  # list of connections made by `connect_all`
            if connect == 'before':
                self.connect_all()  # connect signals and events
            if "__init__" in Form.__dict__:
                Form.__init__(self, *args, **kwargs)
            self.splashscreen = None  # delete splash screen
            if connect == 'after':
                self.connect_all()  # connect signals and events

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

        def set_slotname_convention(self, re_str):
            try:
                if not re_str.format(object="A", signal="B").isidentifier():
                    raise Exception("Provided pattern '%s' cannot be used "
                                    "for python identifiers" % re_str)
            except KeyError:
                raise Exception("Provide both {object} and {signal} fields")
            py2_ident = "[a-zA-Z_][a-zA-Z0-9_]*"
            field_tpl = "(?P<{field}>{ident})"
            obj_field = field_tpl.format(field="object", ident=py2_ident)
            meth_field = field_tpl.format(field="signal", ident=py2_ident)
            self.slots_re = re.compile(re_str.format(object=obj_field,
                                                     signal=meth_field))

        def connect_all(self):
            """Connect signals and events to appropriate members.
            Installs event filter if there's /eventFilter/ member.
            Example: def <object>_<signal/slot>():"""
            if self._connections:
                debug("Reconnect all")
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
                for m in members:
                    match = self.slots_re.fullmatch(m)
                    if not match:
                        continue
                    d = match.groupdict()
                    if d.get("object") != i:
                        continue
                    meth_name = d.get("signal")
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

    instance = QtFormWrapper(*args, **kwargs)
    if show:
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
            self.pushButton1 = QtWidgets.QPushButton("Push", self)
            self.setGeometry(200, 200, 200, 200)

        def pushButton1_clicked(self):
            print('Button clicked')

        def paintEvent(self, event):
            p = QtGui.QPainter(self)
            t = "Center of the widget"
            p.setPen(QtGui.QColor("white"))
            p.drawText(event.rect().translated(1, 1), Qt.AlignCenter, t)
            p.setPen(QtGui.QColor("gray"))
            p.drawText(event.rect(), Qt.AlignCenter, t)

    options['debug'] = True
    QtForm(Form)
else:
    print("Loaded shared qtapp module (Qt %s)" % QtCore.__version__)
