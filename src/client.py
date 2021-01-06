import os
import logging

from metainfo import Metainfo
from torrent import Torrent
from connection import ConnectionManager

log = logging.getLogger(__name__)


class Client():
    def __init__(self, output_destination=None):
        self.active_torrent = []
        self.finished_torrent = []
        self.output_destination = output_destination
        self.conn_man = ConnectionManager()

    def add_torrent(self, filename):
        with open(filename, 'rb') as f:
            contents = f.read()
        metainfo = Metainfo(contents)
        torrent = Torrent(self.conn_man, metainfo, self.torrent_on_completed, self.piece_on_complete)
        self.active_torrent.append(torrent)

    def start_torrents(self):
        for torrent in self.active_torrent:
            torrent.start_torrent()
        self.conn_man.start_event_loop()

    def piece_on_complete(self, torrent):
        print('%s: %s' % (torrent, torrent.progress_bar()))

    def torrent_on_completed(self, torrent, data):
        print('Torrent completed!')
        if torrent.metainfo.info['format'] == 'SINGLE_FILE':
            self.single_file_save(torrent, data)
        else:
            self.multiple_file_save(torrent, data)

        self.active_torrent.remove(torrent)
        self.finished_torrent.append(torrent)

        if not self.active_torrent:
            self.on_all_torrent_completed()

    def on_all_torrent_completed(self):
        self.conn_man.stop_event_loop()

    def single_file_save(self, torrent, data):
        (_, filename) = os.path.split(torrent.metainfo.name)
        filepath = (os.path.join(os.path.expanduser(self.output_destination), filename) if self.output_destination else filename)
        with open(filepath, 'wb') as f:
            f.write(data)

    def multiple_file_save(self, torrent, data):
        begin = 0
        base_dir = torrent.metainfo.name
        base_dir = (os.path.join(os.path.expanduser(self.output_destination), base_dir) if self.output_destination else base_dir)
        for file_dict in torrent.metainfo.info['files']:
            filepath = os.path.join(base_dir, file_dict['path'])
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file_data = data[begin: begin+file_dict['length']]
            with open(filepath, 'wb') as f:
                f.write(file_data)
            begin += file_dict['length']
        if begin != len(data):
            log.warn('begin != len(data)')
