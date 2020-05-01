#! /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from optparse import OptionParser
import data
import model

# import config
from datetime import datetime


def main():
    usage = "usage: %prog [options] DIRNAME"
    parser = OptionParser(usage)
    parser.add_option("-e", "--example", type="string", dest="example",
                      default="value", metavar="[value1|value2]", help="Explanation [default: %default]")
    (options, args) = parser.parse_args()  # by default it uses sys.argv[1:]
    if not len(args) == 1:
        parser.error("Directory missing")

    dirname = args[0]
    instance = data.Data(dirname)


if __name__ == "__main__":
    main()
