# qtapp

`qtapp` helps to create Qt5 GUI with as little source code as possible.

![src1](https://user-images.githubusercontent.com/53390/33850261-5bd04746-dec4-11e7-884f-f5b52d67755e.PNG)

Features:
* Load UI-file
* Compile resources
* Connect signals and events
* Add tray icon
* Show splash screen

Requirements:
* PyQt / PySide
* qtpy
* pathlib (Python 3.4+)

Documentation:
````
`exec_()` - start main event loop
`QtApp` - QApplication subclass
  Members:
  `path` - application path
  `load_resources` - load specified .qrc-file
`app()` - `QtApp` instance, creates a new one on 1st call
`QtForm()` - create new Qt window (and `QtApp` instance if needed). Arguments
             can be provided in variables of user class: _argname_ = value
  Arguments:
  `Form` - user class to use as a subclass of `QWidget` (explicitly specify
           super class [QDialog|QWidget|QMainWindow] if ui-file is not used)
  `*args`=() - additional arguments for user class `__init__`
  `flags`=None - Qt.WindowFlags
  `ui`=None - path to .ui-file, if `None` try lowercase name of `Form` class
  `ontop`=False - show window always on top, adds `WindowStaysOnTopHint` flag
                  to `flags`.
  `icon`=None - set window icon: QIcon|QStyle.StandardPixmap|image-path.
                `SP_TitleBarMenuButton` icon is used by default
  `show`=True - show window by default. Always True if `splash` provided.
  `tray`=None - add tray icon: True (use QtForm window icon)|dict
      Arguments:
      {`tip` - tray icon tooltip,
       `icon` - custom icon (see `QtForm` `icon` arg)}
  `splash`=None - show splash screen: str|pathlib.Path|dict
                  Pass image path only or options dict.
      Arguments:
      {`image` - path to splash screen image file,
       `title`="Loading application..." - caption on the splash screen,
       `align`=Qt.AlignHCenter|Qt.AlignBottom - caption alignment,
       `color`=Qt.black - caption color}
  `loop`=False - do not return and start main event loop
  `connect`=True - call `connect_all()` after initialization
  `**kwargs`=() - additional keyword arguments for user class `__init__`.
                  To pass additional arguments to base class `__init__` use
                  keywords with `_super` postfix.
  Members:
  `app` - `QtApp` instance
  `tray` - `QSystemTrayIcon` if created or None
      Members:
      `addMenuItem(name1, func1, ...)` - add 1 or more context menu items
  `connect_all()` - connects events and signals to appropriate members:
                   def ObjName_SignalName(...), special: def eventFilter(...)
                   Note: Use `self` as `ObjName` of `QtForm` signal handlers
  `init_tray()` - init. tray icon manually, see `tray` arg. of `QtForm`
  `splashscreen` - `QSplashScreen` if created or None. After _init_ it's None
````
