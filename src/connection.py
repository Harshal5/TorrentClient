import logging
import socket
import queue
import time
import threading

log = logging.getLogger(__name__)

class ConnectionManagerThreaded():
    def __init__(self):
        self.conns = []
        self.loop_active = False

    def connect_peer(self, peer):
        conn = PeerConnectionThreaded(peer)
        self.conns.append(conn)

    def start_event_loop(self):
        self.loop_active = True
        while self.loop_active:
            time.sleep(0)
            for conn in self.conns:
                if not conn.thread.is_alive():
                    continue
                conn.check_events()

    def stop_event_loop(self):
        self.loop_active = False
        for conn in self.conns:
            conn.disconnect()

class PeerConnectionThreaded():
    def __init__(self, peer):
        self.peer = peer
        self.is_stopped = False

        self.receive_queue = queue.Queue()
        self.write_queue = queue.Queue()
        self.connect_event = threading.Event()
        self.disconnect_event = threading.Event()
        self.connection_succeeded = threading.Event()
        self.connection_failed = threading.Event()
        self.connection_lost = threading.Event()

        self.thread = PeerConnectionThreadedThread(self)
        self.thread.start()
        self.connect()

    def check_events(self):
        if not self.receive_queue.empty():
            try:
                data = self.receive_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                self.handle_data_received(data)

        if self.connection_succeeded.is_set():
            self.connection_succeeded.clear()
            self.handle_connection_succeded()
        if self.connection_failed.is_set():
            self.connection_failed.clear()
            self.handle_connection_failed()
        if self.connection_lost.is_set():
            self.connection_lost.clear()
            self.handle_connection_lost()

    def handle_connection_succeded(self):
        self.peer.handle_connection_made(self)

    def handle_connection_failed(self):
        self.peer.handle_connection_failed()

    def handle_connection_lost(self):
        self.peer.handle_connection_lost()

    def handle_data_received(self, data):
        self.peer.handle_data_received(data)

    def connect(self):
        self.connect_event.set()

    def write(self, data):
        self.write_queue.put(data)

    def disconnect(self):
        self.disconnect_event.set()

class PeerConnectionFailedError(Exception):
    pass

class PeerConnectionThreadedThread(threading.Thread):
    def __init__(self, conn):
        self.ip = conn.peer.ip
        self.port = conn.peer.port

        self.receive_queue = conn.receive_queue
        self.write_queue = conn.write_queue
        self.connect_event = conn.connect_event
        self.disconnect_event = conn.disconnect_event
        self.connection_succeeded = conn.connection_succeeded
        self.connection_failed = conn.connection_failed
        self.connection_lost = conn.connection_lost

        threading.Thread.__init__(self)

    def run(self):
        self.connect_event.wait()
        try:
            self.thread_connect()
        except PeerConnectionFailedError:
            self.connection_failed.set()
            self.sock.close()
            self.sock = None
            return

        while not self.disconnect_event.is_set():
            time.sleep(0)
            self.thread_send()
            self.thread_receive()

        self.sock.close()
        self.sock = None

    def thread_connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(3.0)
        try:
            self.sock.connect((self.ip, self.port))
        except OSError:
            raise PeerConnectionFailedError

        self.sock.setblocking(False)
        self.connection_succeeded.set()

    def thread_send(self):
        while True:
            try:
                data = self.write_queue.get_nowait()

                try:
                    self.sock.send(data)
                except BrokenPipeError:
                    self.thread_handle_connection_lost()
                    return
            except queue.Empty:
                return

    def thread_receive(self):
        try:
            data = self.sock.recv(4096)
        except BlockingIOError:
            return
        except ConnectionError:
            self.thread_handle_connection_lost()
            return

        if not data:
            self.thread_handle_connection_lost()
            return

        self.receive_queue.put(data)

    def thread_handle_connection_lost(self):
        self.connection_lost.set()
        self.disconnect_event.set()

ConnectionManager = ConnectionManagerThreaded