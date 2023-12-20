from pymmcore_plus import CMMCorePlus
from pymmcore_widgets._mda._stack_viewer import StackViewer
from pymmcore_widgets._mda._datastore import QLocalDataStore
from useq import MDASequence

from isim_control.settings import iSIMSettings
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.pubsub import Subscriber, Publisher, Broker
from isim_control.mp_pubsub import Relay
from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.gui.save_button import SaveButton

from qtpy.QtCore import QObject, Signal, QTimer
from qtpy.QtWidgets import QWidget
import time

import multiprocessing
import numpy as np


def writer_process(queue, settings, mm_config, out_conn):
    broker = Broker(pub_queue=queue)
    sequence = useq_from_settings(settings)
    writer = OMETiffWriter(settings["path"], settings, mm_config)
    writer.sequenceStarted(sequence)
    broker.attach(writer)
    out_conn.send(True)


class OutputGUI(QWidget):
    acquisition_started = Signal()
    def __init__(self, mmcore: CMMCorePlus):
        super().__init__()
        self.mmc = mmcore

        routes = {"acquisition_start": [self._on_acquisition_start],
                  "settings_change": [self._on_settings_change],
                  "live_button_clicked": [self._on_live_toggle],}
        self.sub = Subscriber(["gui"], routes)
        self.settings = iSIMSettings()
        self.acquisition_started.connect(self.make_viewer)
        view_settings = load_settings("live_view")
        self.transform = (view_settings.get("rot", 0),
                          view_settings.get("mirror_x", False),
                          view_settings.get("mirror_y", True))
        self.last_live_stop = time.perf_counter()

        self.mm_config = None
        self.viewer = None
        self.relay = None

    def _on_settings_change(self, keys, value):
        self.settings.set_by_path(keys, value)

    def _on_acquisition_start(self, toggled):
        self.acquisition_started.emit()

    def make_viewer(self):
        if self.relay:
            self.relay.pub.publish("stop", "stop", [])
        if self.viewer:
            self.save_button.close()
            del self.viewer

        shape = self.get_shape(self.settings)
        self.datastore = QLocalDataStore(shape, mmcore=self.mmc)
        if self.settings['save']:
            self.relay = Relay(self.mmc)
            self.ext_p = multiprocessing.Process(target=writer_process,
                                                 args=([self.relay.pub_queue,
                                                        self.settings,
                                                        self.mmc.getSystemState().dict(),
                                                        self.relay.out_conn]))
            self.ext_p.start()
            self.relay.in_conn.recv()

        self.size = (self.mmc.getImageHeight(), self.mmc.getImageWidth())
        # Delay the creation of the viewer so that the preview can finish
        delay = int(max(0, 1200 - (time.perf_counter() - self.last_live_stop)*1000))
        self.timer = QTimer.singleShot(delay, self.create_viewer)

    def create_viewer(self):
        self.viewer = StackViewer(datastore=self.datastore, mmcore=self.mmc,
                                  sequence=useq_from_settings(self.settings),
                                  size=self.size, transform=self.transform)
        self.save_button = SaveButton(self.datastore, self.viewer.sequence, self.settings,
                                      self.mm_config)
        self.viewer.bottom_buttons.addWidget(self.save_button)
        self.viewer.show()

    def get_shape(self, settings:dict):
        sequence = useq_from_settings(settings)
        sizes = sequence.sizes
        shape = [sizes.get('t', 1), sizes.get('z', 1), sizes.get('c', 1), sizes.get('g', 1),
                 self.mmc.getImageHeight(), self.mmc.getImageWidth()]
        return shape

    def _on_live_toggle(self, toggled):
        if not toggled:
            self.last_live_stop = time.perf_counter()

    def close_processes(self):
        self.relay.pub.publish("stop", "stop", [])
