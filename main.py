#! /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import argparse

import data
import model


def main():
    parser = argparse.ArgumentParser(description='MILP solver for timetabling.')
    parser.add_argument(dest="dirname", type=str, help='dirname')
    parser.add_argument("-e", "--example", type=str, dest="example",
                        default="value", metavar="[value1|value2]", help="Explanation [default: %default]")

    args = parser.parse_args()  # by default it uses sys.argv[1:]

    instance = data.Data(args.dirname)
    rooms = {'Odense U151': instance.rooms.get('Odense U151'),'Odense U154':instance.rooms.get('Odense U163'),'Odense U163':instance.rooms.get('Odense U163')}
    m = model.Model(instance.events,instance.slots,instance.banned,rooms,instance.teachers)
    result = m.CTT(1)#m.CTT(m.weeks_end-m.weeks_begin+1)
    # m.write_time_table_for_course(result,[course for course in m.courses])


if __name__ == "__main__":
    main()
