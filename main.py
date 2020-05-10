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
    slots,banned = instance.slots,instance.banned
    m = model.Model(instance.events,instance.slots,instance.banned,{1:{"size":20}},instance.teachers)
    result = m.CTT(1)
    m.write_time_table_for_course(result,["DM803"])
    # print(m.set_of_weeks.get('week 6'))
    # print(m.get_events_this_week(6))
    # print(m.events.get(1758))
    # print({key:value for key,value in m.timeslots.items() if value not in m.banned})


if __name__ == "__main__":
    main()
