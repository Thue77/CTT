#! /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import argparse

import data
import model
import time
import pandas as pd
import csv


def main():
    parser = argparse.ArgumentParser(description='MILP solver for timetabling.')
    parser.add_argument(dest="dirname", type=str, help='dirname')
    parser.add_argument("-e", "--example", type=str, dest="example",
                        default="value", metavar="[value1|value2]", help="Explanation [default: %default]")

    args = parser.parse_args()  # by default it uses sys.argv[1:]

    instance = data.Data(args.dirname)
    m = model.Model(instance.events,instance.slots,instance.banned,instance.rooms,instance.teachers,instance.students)
    start = time.time()
    final = m.CTT()
    # pd.set_option('display.max_rows', None)
    # pd.set_option('display.max_columns', None)
    # pd.set_option('display.width', None)
    # pd.set_option('display.max_colwidth', None)
    print("Time: ",time.time()-start)
    week_dict = m.write_time_table_for_course(final[1],[course for course in m.courses],[w for w in range(m.weeks_begin,m.weeks_end+1)])
    room_dict = m.write_time_table_for_room(final[1],[r for r in m.rooms.values()],[w for w in range(m.weeks_begin,m.weeks_end+1)])
    print("Week 14 \n {}".format(week_dict.get("Week 14")))
    # with open('weeks.csv', 'w') as f:
    #     writer = csv.writer(f)
    #     writer.writerow([week for week in week_dict.keys()])
    #     pd.concat([df for df in week_dict.values()], axis=1).to_csv(f,index=False)
    # for week,rooms in room_dict.items():
    #     with open(week+'.csv','w') as f:
    #         writer = csv.writer(f)
    #         writer.writerow([room for room in rooms.keys()])
    #         pd.concat([df for df in rooms.values()], axis=1).to_csv(f,index=False)

if __name__ == "__main__":
    main()
