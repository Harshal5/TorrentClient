import struct
import requests
import bencodepy
import logging

from settings import SETTINGS

log = logging.getLogger(__name__)


class Tracker():
    def __init__(self, torrent, announce):
        self.torrent = torrent
        self.announce = announce
        self.tracker_id = None

    def announce_request(self):
        http_resp = requests.get(self.announce, {
            'info_hash': self.torrent.metainfo.info_hash,
            'peer_id': SETTINGS['peer_id'],
            'port': 6881,
            'uploaded': '0',
            'downloaded': '0',
            'left': str(self.torrent.metainfo.info['length'])
        })
        self.announce_response(http_resp)
    
    def announce_response(self, http_resp):
        resp = bencodepy.decode(http_resp.content)
        d = self.decode_announce_response(resp)
        for peer_dict in d['peers']:
            if peer_dict['ip'] and peer_dict['port'] > 0:
                self.torrent.add_peer(peer_dict)
   
    @classmethod
    def decode_announce_response(cls, resp):
        d = {}
        d['interval'] = int(resp[b'interval'])
        d['complete'] = int(resp[b'complete']) if b'complete' in resp else None
        d['incomplete'] = (int(resp[b'incomplete']) if b'incomplete' in resp else None)
        try:
            d['tracker_id'] = resp[b'tracker id'].decode('utf-8')
        except KeyError:
            d['tracker_id'] = None

        raw_peers = resp[b'peers']
        if isinstance(raw_peers, list):
            d['peers'] = cls.decode_dict_model_peers(raw_peers)
        elif isinstance(raw_peers, bytes):
            d['peers'] = cls.decode_binary_model_peers(raw_peers)
        else:
            raise AnnounceDecodeError('Invalid peers format: %s' % raw_peers)

        return d

    @staticmethod
    def decode_dict_model_peers(peers_dicts):
        # print(x)
        return [{'ip': d[b'ip'].decode('utf-8'),
                 'port': d[b'port'],
                 'peer_id': d.get(b'peer id')}
                for d in peers_dicts]
    
    @staticmethod
    def decode_binary_model_peers(peers_bytes):
        fmt = '!BBBBH'
        fmt_size = struct.calcsize(fmt)
        if len(peers_bytes) % fmt_size != 0:
            raise AnnounceDecodeError('Binary model peers field length error')
        peers = [struct.unpack_from(fmt, peers_bytes, offset=ofs)
                 for ofs in range(0, len(peers_bytes), fmt_size)]
        return [{'ip': '%d.%d.%d.%d' % p[:4], 'port': int(p[4])} for p in peers]

class AnnounceFailureError(Exception):
    pass


class AnnounceDecodeError(Exception):
    pass
