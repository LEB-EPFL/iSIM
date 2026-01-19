from MicroManagerControl import MicroManagerControl
from gui.GUIWidgets import SettingsView
import sys
from PyQt5 import QtWidgets
from pymm_eventserver.event_thread import EventThread
from gui.MainGUI import MainGUI
from hardware.nidaq import NIDAQ


def main():
    app = QtWidgets.QApplication(sys.argv)

    topics = ["StandardEvent", "GUIRefreshEvent", "LiveMode", "Acquisition",
              "GUI", "Hardware", "Settings"]
    event_thread = EventThread(topics=topics)
    event_listener = event_thread.listener

    mm_interface = MicroManagerControl(event_listener)

    ni = NIDAQ(event_listener, mm_interface)
    settings_view = SettingsView(event_listener)
    miniapp = MainGUI(event_thread=event_listener)
    miniapp.show()

    sys.exit(app.exec_())


def alignment():
    app = QtWidgets.QApplication(sys.argv)

    topics = ["StandardEvent", "GUIRefreshEvent", "LiveMode", "Acquisition",
              "GUI", "Hardware", "Settings", "NewImage"]
    event_thread = EventThread(topics=topics, live_images=True)
    event_listener = event_thread.listener

    mm_interface = MicroManagerControl(event_listener)

    ni = NIDAQ(event_listener, mm_interface)
    settings_view = SettingsView(event_listener)
    miniapp = MainGUI(event_thread=event_listener, alignment=True, monogram=False)
    miniapp.show()

    sys.exit(app.exec_())


flavours = {"main": main, "alignment": alignment}
try:
    flavour = flavours[sys.argv[1]]
except IndexError:
    print("No mode specified, running main")
    flavour = main


if __name__ == "__main__":
    flavour()
