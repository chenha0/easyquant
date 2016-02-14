# coding: utf-8
import time
from threading import Thread
from .event_engine import Event
from .event_type import EventType
from . import easyquotation


class Quotation:
    """行情推送引擎"""

    def __init__(self, event_engine):
        self.event_engine = event_engine
        self.is_active = True
        self.source = easyquotation.use('lf')
        self.quotation_thread = Thread(target=self.get_quotation)
        self.sleep_time = 1
        self.max_queue_size = 3

    def start(self):
        self.quotation_thread.start()

    def get_quotation(self):
        while self.is_active:
            if self.event_engine.queue_size > self.max_queue_size:
                self.sleep_time *= 2
            response_data = self.source.stocks([
                '502003', '502004', '502005',
                '502006', '502007', '502008',
                '502010', '502011', '502012',
                '502013', '502014', '502015',
                '502036', '502037', '502038',
                '502048', '502049', '502050',
                ])
            event = Event(event_type=EventType.QUOTATION, data=response_data)
            self.event_engine.put(event)
            time.sleep(self.sleep_time)

    def stop(self):
        self.is_active = False

if __name__ == '__main__':
    pass
