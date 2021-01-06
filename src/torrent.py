import hashlib
import logging

from settings import SETTINGS
from peer import Peer
from tracker import Tracker

log = logging.getLogger(__name__)

class Torrent():
    def __init__(self, conn_man, metainfo, torrent_on_completed=None, piece_on_complete=None):
        self.metainfo = metainfo
        self.conn_man = conn_man
        self.active_peers = []
        self.peers = []
        self.tracker = None
        self.is_complete = False

        self.torrent_on_completed = torrent_on_completed
        self.piece_on_complete = piece_on_complete

        self.piece_blocks = [[] for _ in self.metainfo.info['pieces']]
        self.piece_requests = [[] for _ in self.metainfo.info['pieces']]
        self.complete_pieces = [None for _ in self.metainfo.info['pieces']]

    def start_torrent(self):
        self.tracker = Tracker(self, self.metainfo.announce)
        self.tracker.announce_request()
        for peer in self.peers[:SETTINGS['max_peers']]:
            peer.connect()

    def add_peer(self, peer_dict):
        peer = self.find_peer(**peer_dict)
        if peer:
            return peer
        peer = Peer(self, **peer_dict)
        self.peers.append(peer)
        return peer

    def find_peer(self, ip, port, **kwargs):
        for peer_list in (self.active_peers, self.peers):
            for v in peer_list:
                if v.ip == ip and v.port == port:
                    return v
        return None

    def handle_block(self, peer, piece_index, begin, block):
        if self.complete_pieces[piece_index]:
            return
        for v in self.piece_blocks[piece_index]:
            if v[0] == begin:
                peer.request_new_block(piece_index, begin)
                return
        self.piece_blocks[piece_index].append((begin, block))

        expected_length = self.metainfo.get_piece_length(piece_index)
        piece_length = sum(len(v[1]) for v in self.piece_blocks[piece_index])
        if piece_length == expected_length:
            self.handle_completed_piece(peer, piece_index)
        else:
            peer.request_new_block(piece_index, begin)

    def handle_completed_piece(self, peer, piece_index):
        if self.complete_pieces[piece_index] is not None:
            log.warning('Piece %d already completed' % piece_index)
            return
        self.piece_blocks[piece_index].sort(key=lambda v: v[0])
        blocks = [v[1] for v in self.piece_blocks[piece_index]]
        piece = bytes(v for block in blocks for v in block)
        piece_sha = hashlib.sha1(piece).digest()
        isSame_sha = self.metainfo.info['pieces'][piece_index]
        if piece_sha != isSame_sha:
            raise TorrentPieceError('Piece %d sha mismatch')
        self.complete_pieces[piece_index] = piece
        self.piece_blocks[piece_index] = None
        for p in self.piece_requests[piece_index]:
            if p.requested_piece == piece_index:
                p.requested_piece = None
            if p != peer:
                pass
        self.piece_requests[piece_index] = None
        log.debug('handle_completed_piece: %d' % piece_index)
        if self.piece_on_complete:
            self.piece_on_complete(self)
        peer.run_download()
        if not any(v is None for v in self.complete_pieces):
            self.handle_completed_torrent()

    def progress_bar(self):
        num_complete = sum(v is not None for v in self.complete_pieces)
        num_pieces = len(self.complete_pieces)
        pct_complete = 100.0 * num_complete / num_pieces
        return('%s / %s (%02.1f%%) complete' % (num_complete, num_pieces, pct_complete))

    def handle_completed_torrent(self):
        log.info('%s: handle_completed_torrent' % (self))
        self.is_complete = True
        data = bytes(v for piece in self.complete_pieces for v in piece)
        for p in self.peers:
            p.handle_torrent_completed()
        if self.torrent_on_completed:
            self.torrent_on_completed(self, data)

    def handle_peer_stopped(self, peer):
        if self.is_complete:
            return
        num_active = sum(1 for p in self.peers if p.is_started and not p.conn_failed)
        if num_active >= SETTINGS['max_peers']:
            return
        for p in self.peers[SETTINGS['max_peers']:]:
            if p.conn or p.is_started or p.conn_failed:
                continue
            log.info('handle_peer_stopped: starting new peer: %s' % p)
            p.connect()
            break

class TorrentPieceError(Exception):
    pass
