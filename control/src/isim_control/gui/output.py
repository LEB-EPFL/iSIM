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
    def __init__(self, mmcore: CMMCorePlus, settings: iSIMSettings, broker: Broker):
        super().__init__()
        self.mmc = mmcore
        self.broker = broker
        self.relay = CMMCRelay(self.broker.pub_queue, self.mmc)

        routes = {"acquisition_start": [self.make_viewer],
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

        self.last_live_stop = time.perf_counter()
        self.mm_config = None
        self.viewer = None
        self.start_processes()

    def _on_acquisition_end(self):
        self.close_remote_brokers()
        self.start_processes()

    def start_processes(self):
        self.writer_process = multiprocessing.Process(target=tiff_writer_process,
                                                 args=([self.writer_relay.pub_queue,
                                                        self.settings,
                                                        self.mmc.getSystemState().dict(),
                                                        self.writer_relay.in_conn,
                                                        self.buffered_datastore._shm.name]),
                                                 name="writer")
        self.writer_process.start()

        self.viewer_process = multiprocessing.Process(target=viewer_process,
                                                 args=([self.viewer_relay.pub_queue,
                                                        self.viewer_relay.in_conn,
                                                        self.buffered_datastore._shm.name]),
                                                 name="viewer")
        self.viewer_process.start()


    def make_viewer(self, settings:dict = None):
        self.size = (self.mmc.getImageHeight(), self.mmc.getImageWidth())
        self.viewer_relay.pub.publish("gui", "acquisition_start", [useq_from_settings(self.settings)])
        self.activate_remotes()
        if self.settings['save']:
            self.writer_relay.pub.publish("datastore", "reset", [self.settings, self.mmc.getSystemState().dict()])
        else:
            self.writer_relay.pub.publish("stop", "stop", [])

    def get_shape(self, settings:dict):
        sequence = useq_from_settings(settings)
        sizes = sequence.sizes
        shape = [sizes.get('t', 1), sizes.get('z', 1), sizes.get('c', 1), sizes.get('g', 1),
                 self.mmc.getImageHeight(), self.mmc.getImageWidth()]
        return shape

    def _on_live_toggle(self, toggled):
        if not toggled:
            self.last_live_stop = time.perf_counter()

    def close_remote_brokers(self):
        self.writer_relay.pub.publish("stop", "stop", [])
        self.viewer_relay.pub.publish("stop", "stop", [])

    def activate_remotes(self):
        self.writer_relay.out_conn.send(True)
        self.viewer_relay.out_conn.send(True)

    def shutdown(self):
        self.writer_relay.pub.publish("stop", "stop", [])
        self.viewer_relay.pub.publish("gui", "shutdown", [])
        self.viewer_relay.pub.publish("stop", "stop", [])

        self.writer_relay.out_conn.send(False)
        self.viewer_relay.out_conn.send(False)
        self.writer_process.join()
        print("Writer process closed")
        self.viewer_process.join()
        print("Viewer process closed")