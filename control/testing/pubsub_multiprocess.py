from isim_control.pubsub import Subscriber, Publisher, Broker
import multiprocessing
import time



class Suber():
    def __init__(self):
        routes = {"live_button_clicked": [self.got_it]}
        self.sub = Subscriber(["gui"], routes)

    def got_it(self, value):
        print("got it")

def make_suber(queue):
    broker = Broker(pub_queue=queue)
    sub = Suber()
    broker.attach(sub)

if __name__ == "__main__":

    queue = multiprocessing.Queue()
    pub = Publisher(queue)
    p = multiprocessing.Process(target=make_suber, args=([queue]))
    p.start()
    time.sleep(3)
    pub.publish("gui", "live_button_clicked", [True])
    print("Signal sent")
