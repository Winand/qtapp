from qtapp import QtForm, QtWidgets


class Page(QtWidgets.QWizardPage):
    _layout_ = QtWidgets.QVBoxLayout
    _show_ = False  # QWizard handles this

    def __init__(self, btn_text):
        self.pb = QtWidgets.QPushButton(btn_text, self)
        self.layout().addWidget(self.pb)
        self.txt = QtWidgets.QLineEdit("test string", self)
        self.layout().addWidget(self.txt)

    def pb_clicked(self):
        print(self.txt.text())


class Wizard(QtWidgets.QWizard):
    _loop_ = True
    _ontop_ = True

    def __init__(self):
        for p in QtForm(Page, "Pg.1 button"), QtForm(Page, "Pg.2 button"):
            self.addPage(p)  # "parent is automatically set to be the wizard"


QtForm(Wizard)
