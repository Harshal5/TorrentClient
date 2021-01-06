import sys
import argparse
import logging

from client import Client


def main(argv=None):
    argv = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('torrent', help='.torrent metainfo file')
    parser.add_argument('--d', type=str, help='output directory')
    args = parser.parse_args(argv)
    client = Client(output_destination=args.d)
    client.add_torrent(args.torrent)
    client.start_torrents()

if __name__ == '__main__':
    main()
