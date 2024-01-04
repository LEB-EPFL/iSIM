from __future__ import annotations
import multiprocessing
from _queue import Empty
from threading import Thread

class Broker(Thread):
    def __init__(self, pub_queue: multiprocessing.Queue | None = None,
                 auto_start: bool = True):
        super().__init__()
        self.subscribers = set()
        self.pub_queue = pub_queue or multiprocessing.Queue()
        self.stop_requested = False
        if auto_start:
            self.start()

    def attach(self,subscriber: Subscriber):
        self.subscribers.add(subscriber)

    def route(self, topic, message: str, values: list):
        for subscriber in self.subscribers:
            if topic in subscriber.sub.topics:
                if message in subscriber.sub.routes.keys():
                    subscriber.sub.sub_queue.put({"event": message,
                                                "values": values})
        if topic == "stop":
            self.stop()

    def run(self):
        while True:
            try:
                message = self.pub_queue.get(timeout=0.5)
                print(message['topic'], message['event'])
                self.route(message["topic"], message["event"], message["values"])
            except Empty:
                if self.stop_requested:
                    break
                else:
                    continue

    def stop(self):
        self.stop_requested = True
        for subscriber in self.subscribers:
            subscriber.sub.stop()


class Publisher():
    def __init__(self, pub_queue: multiprocessing.Queue):
        self.pub_queue = pub_queue

    def publish(self, topic, message, values: list = None):
        values = [] if values is None else values
        return self.pub_queue.put({"topic": topic,
                                   "event": message,
                                   "values": values})


class Subscriber(Thread):
    def __init__(self, topics:list[str], routes: dict):
        super().__init__()
        self.topics = topics
        self.routes = routes
        self.sub_queue = multiprocessing.Queue()
        self.stop_requested = False
        self.start()

    def receive(self, message, values: list):
        callbacks = self.routes.get(message, [])
        for callback in callbacks:
            callback(*values)

    def run(self):
        while True:
            try:
                message = self.sub_queue.get(timeout=0.5)
                self.receive(message["event"], message["values"])
            except Empty:
                if self.stop_requested:
                    break
                else:
                    continue

    def stop(self):
        self.stop_requested = True


class GUI:
    def __init__(self, broker:Broker):
        self.pub = Publisher(broker)
        routes = {"live_started": [self._on_live_started]}
        self.sub = Subscriber(["backend"], routes)

    def _on_live_button_clicked(self, value: str):
        self.pub.publish("gui", "live_button_clicked", [value])

    def _on_live_started(self, value):
        state = "sarted" if value else "stopped"
        not_state = "stopped" if value else "sarted"
        print(f"---live {state} received in gui -> change live to {not_state}---")

    def stop(self):
        self.sub.stop()

class Backend:
    def __init__(self, broker: Broker):
        self.pub = Publisher(broker)
        routes = {"live_button_clicked": [self._on_live_requested]}
        self.sub = Subscriber(["gui"], routes)


    def _on_live_requested(self, value):
        state = "sarted" if value else "stopped"
        print(f"---live {state} in backend---")
        self.pub.publish("backend", "live_started", [value])

    def stop(self):
        self.sub.stop()



if __name__ == "__main__":
    import time
    broker = Broker()
    broker.start()

    backend = Backend(broker.pub_queue)
    gui = GUI(broker.pub_queue)

    broker.attach(backend)
    broker.attach(gui)

    gui._on_live_button_clicked(True)
    time.sleep(3)
    gui._on_live_button_clicked(False)


    print("Done")
    broker.stop()
    gui.stop()
    backend.stop()
