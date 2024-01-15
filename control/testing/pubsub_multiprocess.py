from isim_control.pubsub import Subscriber, Publisher, Broker
import multiprocessing
import time

from qtpy import QtWidgets, QtCore


class Suber(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        routes = {"live_button_clicked": [self.got_it],
                  "close_windows": [self.close_me]}
        self.sub = Subscriber(["gui", "stop"], routes)

    def got_it(self, value):
        print("got it")

    def close_me(self, close):
        print("Close requested")
        QtCore.QTimer.singleShot(1000, self.close)
        print("CLOSING")


def make_suber(queue):
    app = QtWidgets.QApplication([])
    broker = Broker(pub_queue=queue)
    sub = Suber()
    broker.attach(sub)
    sub.show()
    app.exec_()
    print("App in process ended")

if __name__ == "__main__":
    queue = multiprocessing.Queue()
    pub = Publisher(queue)
    p = multiprocessing.Process(target=make_suber, args=([queue]))
    p.start()
    time.sleep(3)
    pub.publish("gui", "live_button_clicked", [True])
    print("Signal sent")
    time.sleep(2)
    pub.publish("gui", "close_windows", [True])
    pub.publish("stop", "stop", [True])
    print("Stop sent")
