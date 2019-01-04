#! /usr/bin/python

import sys
import argparse

from rtarchive import LimitReached, UserArchiver, VERSION


BASE_URL = "https://roosterteeth.com/user/"

parser = argparse.ArgumentParser(description='Scrape an RT forum')

parser.add_argument("username", type=str, help="Username of user to scrape")
parser.add_argument("content", type=str, help="Images or Journals")
parser.add_argument("-p", "--path", type=str, default='',
                    help="Path to directory")
parser.add_argument("-m", "--max", type=int, default=0,
                    help="Max number of items to parse; 0 for unlimited")
parser.add_argument("-s", "--size", type=int, default=25,
                    help="Max number of journal pages per file")
parser.add_argument('-V', '--version', action='store_true',
                    help="Print version and exit")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Print debug")


def main():
    args = parser.parse_args()
    user = UserArchiver(args.max, args.size, args.path, args.verbose,
                        args.username)

    if args.version:
        print(user.get_version())
        return 0

    user.logger.debug("Username: %s", args.username)
    user.logger.debug("Path: %s", args.path)
    user.logger.debug("Max items: %d", args.max)
    user.logger.debug("Items per file: %d", args.size)
    user.logger.debug("Content type: %s", args.content)
    try:
        if args.content.lower() == "journals":
            user.get_journals()
        elif args.content.lower() == "images":
            try:
                user.get_images()
                user.get_albums()
            except LimitReached:
                pass
        else:
            user.logger.error("Invalid content type %s", args.content)
            parser.print_usage()
            return -1
    except IOError:
        return -1
    return 0


if __name__ == "__main__":
    sys.exit(main())
