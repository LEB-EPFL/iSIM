from pymmcore_plus import CMMCorePlus


from isim_control.settings import iSIMSettings
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.pubsub import Subscriber, Broker, Publisher
from isim_control.mp_pubsub import Relay, tiff_writer_process, viewer_process

# from isim_control.gui.save_button import SaveButton
from isim_control.io.buffered_datastore import BufferedDataStore


from qtpy.QtCore import Signal, QTimer
from qtpy.QtWidgets import QWidget
import time

import multiprocessing
import numpy as np
from _queue import Empty


class CMMCRelay(Publisher):
    def __init__(self, pub_queue: multiprocessing.Queue, mmcore: CMMCorePlus):
        super().__init__(pub_queue)
        self._mmc = mmcore
        self._mmc.mda.events.sequenceFinished.connect(self.sequenceFinished)

    def sequenceFinished(self):
        self.publish("sequence", "acquisition_end", [])


class OutputGUI(QWidget):
    acquisition_started = Signal()
    def __init__(self, mmcore: CMMCorePlus, settings: iSIMSettings, broker: Broker):
        super().__init__()
        self.mmc = mmcore
        self.broker = broker
        self.relay = CMMCRelay(self.broker.pub_queue, self.mmc)

        routes = {"acquisition_start": [self._on_acquisition_start],
                  "acquisition_end": [self._on_acquisition_end],
                  #"settings_change": [self._on_settings_change],
                  "live_button_clicked": [self._on_live_toggle],}
        self.sub = Subscriber(["gui", "sequence"], routes)
        self.broker.attach(self)

        self.writer_relay = Relay(self.mmc)
        self.viewer_relay = Relay(self.mmc)
        self.buffered_datastore = BufferedDataStore(mmcore=self.mmc, create=True,
                                                    publishers=[self.writer_relay.pub,
                                                                self.viewer_relay.pub])

        self.settings = settings
        self.acquisition_started.connect(self.make_viewer)

        self.last_live_stop = time.perf_counter()
        self.mm_config = None
        self.viewer = None

    def _on_acquisition_start(self, toggled):
        self.acquisition_started.emit()

    def _on_acquisition_end(self):
        print("ACQUSITION ENDED CLOSING STOPPING BROKERS")
        self.close_processes()

    def make_viewer(self, settings:dict = None):
        self.writer_process = multiprocessing.Process(target=tiff_writer_process,
                                                 args=([self.writer_relay.pub_queue,
                                                        self.settings,
                                                        self.mmc.getSystemState().dict(),
                                                        self.writer_relay.out_conn,
                                                        self.buffered_datastore._shm.name]))
        self.writer_process.start()

        self.viewer_process = multiprocessing.Process(target=viewer_process,
                                                 args=([self.viewer_relay.pub_queue,
                                                        self.viewer_relay.out_conn,
                                                        self.buffered_datastore._shm.name]))
        self.viewer_process.start()
        self.size = (self.mmc.getImageHeight(), self.mmc.getImageWidth())
        self.viewer_relay.pub.publish("datastore", "reset", [self.settings, self.size])
        if self.settings['save']:
            self.writer_relay.pub.publish("datastore", "reset", [self.settings, self.size])

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
        self.writer_relay.pub.publish("stop", "stop", [])
        self.viewer_relay.pub.publish("stop", "stop", [])
