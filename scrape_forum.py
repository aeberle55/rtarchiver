#! /usr/bin/python

import sys
import argparse

from rtarchive import ForumArchiver

parser = argparse.ArgumentParser(description='Scrape an RT forum')

parser.add_argument("url", type=str, help="Base URL of the forum page")
parser.add_argument("-p", "--path", type=str, default='',
                    help="Path to directory")
parser.add_argument("-m", "--max", type=int, default=0,
                    help="Max number of pages to parse; 0 for unlimited")
parser.add_argument("-s", "--size", type=int, default=25,
                    help="Max number of pages per file")
parser.add_argument("-b", "--base", type=str, default='',
                    help="Base name for files")
parser.add_argument('-v', '--verbose', action='store_true', help="Print debug")


def main():
    args = parser.parse_args()
    forum = ForumArchiver(args.max, args.size, args.path, args.verbose,
                          args.url, args.base)

    forum.logger.debug("Url: %s", args.url)
    forum.logger.debug("Path: %s", args.path)
    forum.logger.debug("Max pages: %d", args.max)
    forum.logger.debug("Pages per file: %d", args.size)
    forum.logger.debug("Base name of files: %s", args.base)
    return forum.parse_thread()

if __name__ == "__main__":
    sys.exit(main())
