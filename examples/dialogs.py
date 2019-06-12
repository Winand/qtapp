from qtapp import QtForm, Dialog, QtWidgets


class MainForm():
    _loop_ = True
    _layout_ = QtWidgets.QVBoxLayout

    def __init__(self):
        self.pushButton1 = QtWidgets.QPushButton("Show dialog", self)
        self.layout().addWidget(self.pushButton1)
        self.setGeometry(200, 200, 640, 480)
        self.lw = QtWidgets.QListWidget(self)
        self.layout().addWidget(self.lw)
        self.startTimer(500)
        self.top_wgts = {}

    def timerEvent(self, event):
        wgts = {str(i) for i in self.app.topLevelWidgets()}
        if self.top_wgts != wgts:
            self.top_wgts = wgts
            self.lw.clear()
            self.lw.addItems(wgts)

    def pushButton1_clicked(self):
        answ = Dialog(UserDialog)
        code = "accepted" if answ[0] else "rejected"
        print(f"Dialog {code}: {answ[1]}")


class UserDialog():
    _layout_ = QtWidgets.QVBoxLayout

    def __init__(self):
        self.ret = 'answer'
        self.pb1 = QtWidgets.QPushButton(f"Accept with msg '{self.ret}'", self)
        self.layout().addWidget(self.pb1)
        self.pb2 = QtWidgets.QPushButton(f"Reject with msg '{self.ret}'", self)
        self.layout().addWidget(self.pb2)

    def pb1_clicked(self):
        self.accept(self.ret)

    def pb2_clicked(self):
        self.reject(self.ret)

    def __del__(self):
        print("Dialog widget deleted")


QtForm(MainForm)
