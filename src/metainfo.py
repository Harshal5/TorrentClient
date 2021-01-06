import os
import hashlib
import bencodepy

class Metainfo():
    def __init__(self, bencontent):
        try:
            content = bencodepy.decode(bencontent)
        except bencodepy.DecodingError as e:
            raise TorrentDecodeError from e
        self.announce = content[b'announce'].decode('utf-8')
        info_dict = content[b'info']
        self.info_hash = hashlib.sha1(bencodepy.encode(info_dict)).digest()
        self.info = self.decode_info_dict(info_dict)

    def decode_info_dict(self, d):
        info = {}
        info['piece_length'] = d[b'piece length']
        SHA_LEN = 20
        pieces_shas = d[b'pieces']
        info['pieces'] = [pieces_shas[i:i+SHA_LEN] for i in range(0, len(pieces_shas), SHA_LEN)]
        self.name = d[b'name'].decode('utf-8')
        files = d.get(b'files')
        if not files:
            info['format'] = 'SINGLE_FILE'
            info['files'] = None
            info['length'] = d[b'length']
        else:
            info['format'] = 'MULTIPLE_FILE'
            info['files'] = []
            for f in d[b'files']:
                path_segments = [v.decode('utf-8') for v in f[b'path']]
                info['files'].append({'length': f[b'length'], 'path': os.path.join(*path_segments)})
            info['length'] = sum(f['length'] for f in info['files'])
        return info

    def get_piece_length(self, index):
        num_pieces = len(self.info['pieces'])
        piece_length = self.info['piece_length']
        if index == num_pieces - 1:    
            return (self.info['length'] - (num_pieces - 1) * piece_length)
        return piece_length

class TorrentDecodeError(Exception):
    pass
