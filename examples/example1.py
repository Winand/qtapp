# -*- coding: utf-8 -*-

from qtapp.qtapp import QtForm


class Example1():
    _loop_ = True

    def pb_clicked(self):
        print(self.txt.text())

QtForm(Example1)
