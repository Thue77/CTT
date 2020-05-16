import pyomo
import pyomo.opt
import pyomo.environ as pe
import pandas as pd
import preprocessing as pre
import data
from typing import Dict,List,Tuple,Union
from pyomo.opt import SolverStatus, TerminationCondition


class Model(pre.preprocess):
    """docstring for Model."""
    def __init__(self,events: Dict[str,dict],slots: List[dict],banned:List[dict],rooms: dict,teachers: Dict[int,List[Dict[str,Union[str,int]]]], students: Dict[int,List[Dict[str,Union[str,int]]]]):
        super().__init__(events,slots,banned,rooms,teachers,students)

    def remove_var_close_to_banned(self,Index:List[Tuple[int,int,int]]):
        Index_old = Index.copy()
        Index_new = Index.copy()
        for x in Index_old:
            duration = self.events.get(x[0]).get("duration")
            day = self.timeslots.get(x[1]).get("day")
            week = self.timeslots.get(x[1]).get("week")
            for t_banned in self.banned_keys:
                if  day == self.timeslots.get(t_banned).get("day") and week == self.timeslots.get(t_banned).get("week") and  and abs(t_banned-x[1]) < duration:
                    Index_new.remove(x)
                    break
            if self.split_timeslots.get('week '+str(w)).get('day '+str(d))[-1] not in self.banned_keys:

        return Index_new

    def matching_rooms(self,result):
        m = pe.ConcreteModel()
        results = sorted(result,key=lambda x: x[1])
        E = {}
        R = {i:(r,t,d) for i,r,t,d in enumerate([(r,t,self.events[e].get('duration')) for e,t in results for r in self.rooms_busy if not any(self.timeslots[l] in self.rooms_busy for l in range(t,t+self.events[e].get('duration')))])}

        # R = {i:x for i,x in enumerate(set([(r,t,m.events[e].get('duration')) for e,t in final[1] for r in m.rooms_busy if not any(m.timeslots.get(l) in m.rooms_busy.get(r) for l in range(t,t+m.events[e].get('duration')))]))}
# R
# final
# m.rooms_busy
# m.events[0]
        for i,e,t in enumerate(results):
            E[i] = (e,t)
            d_e = self.events.get(e).get('duration')
            for room in self.rooms:
                pass
        E = {i:event for i,event in enumerate(result)}
        periods = set([event[1] for event in E.values()])
        periods = [self.periods.get(p) for p in periods]
        R_list = [(r,period) for r in self.rooms for period in periods if all(p not in self.rooms_busy.get(r) for p in period)]
        R = {i:room for i,room in enumerate(R_list)}
        #Identify rooms with overlapping periods. Only one of such a pair of rooms may be chosen
        pairs = [(i,j) for i in range(len(R)-1) for j in range(i+1,len(R)) if abs(super(Model,self).get_dict_key(self.periods,R[i][1])-super(Model,self).get_dict_key(self.periods,R[j][1]))==1 and R[i][0]==R[j][0]]

        A = [(i,j) for i,e in E.items() for j,room in R.items() if self.periods.get(e[1]) == room[1]]

        m.x = pe.Var(A,domain=pe.Binary)
        m.obj = pe.Objective(expr=0)
        #Constraints
        #Connections to rooms. Adds redundant constraints
        m.room = pe.Constraint(R.keys(),rule=lambda m,r: sum(m.x[e,r] for e in E if (e,r) in A)<=1 if any((e,r) in A for e in E) else pe.Constraint.Skip)
        #Connections to events
        m.event = pe.Constraint(E.keys(),rule=lambda m,e: sum(m.x[e,r] for r in R if (e,r) in A)==1 if any((e,r) in A for r in R) else pe.Constraint.Skip)
        #Only one edge for each pair of (r,p) vertices that have overlapping periods
        m.pairs = pe.Constraint(pairs,rule=lambda m,i,j: sum(m.x[e,j] for e,_ in list(filter(lambda x: x[1]==j,A))) + sum(m.x[e,i] for e,_ in list(filter(lambda x: x[1]==i,A)))<=1)
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=False)

        if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
            print ("this is feasible and optimal")
            return "Done",[[(*E.get(i),R.get(j)[0]) for i,j in A if pe.value(m.x[i,j]) ==1 and R.get(j)[1][0].get('week')==w] for w in range(self.weeks_begin,self.weeks_end+1)]
        elif results.solver.termination_condition == TerminationCondition.infeasible:
            print ("do something about it? or exit?")
            return "Not Done"
        else:
            # something else is wrong
            print (str(results.solver))


    #Prints weekly tables for given courses
    def write_time_table_for_course(self,result: List[List[Tuple[Union[int,int]]]],courses: Tuple[str],week_numbers: List[int]):
        number_of_weeks = len(result)
        for w,week_result in enumerate(result):
            week = w + self.weeks_begin
            if week in week_numbers:
                # Set up empty table
                table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
                temp = []
                for room in self.rooms:
                    for busy in self.rooms_busy.get(room):
                        if busy not in temp and all(busy in rooms_busy for rooms_busy in self.rooms_busy.values()): temp += [busy]
                busy_or_banned = [time for time in temp + self.banned if not (time in temp and time in self.banned)]
                table.update({"day "+str(j):[["busy"] if {'day':j,'hour':i,'week':week} in busy_or_banned  else [] for i in range(self.hours+1)] for j in range(5)})
                for x in week_result:
                    if self.events.get(x[0]).get("id")[0:5] in courses:
                        day = self.periods.get(x[1])[0].get("day")
                        hour = self.periods.get(x[1])[0].get("hour")
                        for i in range(self.period):
                            table["day "+ str(day)][hour+i].append(self.events.get(x[0]).get("id")[0:7])
                print("Week {}\n {}".format(week,pd.DataFrame(table)))


    #Prints time tables for the rooms
    def write_time_table_for_room(self,result: List[List[Tuple[Union[int,int,int]]]],rooms: Tuple[str],week_numbers:[List[int]]):
        number_of_weeks = len(result)
        for w,week_result in enumerate(result):
            week = w + self.weeks_begin
            if week in week_numbers:
                for room in rooms:
                    r = m.get_dict_key(self.rooms,room)
                    # Set up empty table indicating slots that are not available
                    table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
                    busy_or_banned = [time for time in self.rooms_busy.get(r) + self.banned if not (time in self.rooms_busy.get(r) and time in self.banned)]
                    table.update({"day "+str(j):[["busy"] if {'day':j,'hour':i,'week':week} in busy_or_banned  else [] for i in range(self.hours+1)] for j in range(5)})
                    for e,p,r in list(filter(lambda x: x[2] == r,week_result)):
                        day = self.periods.get(p)[0].get("day")
                        hour = self.periods.get(p)[0].get("hour")
                        for i in range(self.period):
                            table["day "+ str(day)][hour+i].append(self.events.get(e).get("id")[0:7])
                    print("Week: {}, Room: {}\n {}".format(week,room,pd.DataFrame(table)))
    def CTT(self):
        m = pe.ConcreteModel()
        #Only include periods without that are not banned
        T = []
        E = []
        Index_old = []
        for week in range(self.weeks_begin,self.weeks_end+1):
            T.append([])
            for day,time_list in self.split_timeslots.get("week "+str(week)).items():
                T[-1].extend([t for t in time_list])
            E.append([key for key in self.get_events_this_week(week)])
            Index_old += [(e,t) for e in E[-1] for t in T[-1]]
        Index = self.remove_var_close_to_banned(Index_old)
        #Define variables
        m.x = pe.Var(Index, domain = pe.Binary)

        #Define objective
        m.obj=pe.Objective(expr=0)

        #Hard constraints
        #All events must happen
        m.events_must_happen = pe.ConstraintList()
        for e in [e for sublist in E for e in sublist]:
            m.events_must_happen.add(sum(m.x[e,t] for _,t in list(filter(lambda x:x[0]==e,Index))) == 1)

        #One event per course per day på student
        # m.one_event_one_day = pe.ConstraintList()
        # for w in range(self.weeks_begin,self.weeks_end+1):
        #     week = "week "+str(w)
        #     W_s = self.split_timeslots.get(week)
        #     S_bar = self.student_events.get(week)
        #     for S in S_bar:
        #         for D in W_s.values():
        #             m.one_event_one_day.add(sum(m.x[e,t] for e in S for t in D)<=1)

        #Ensure feasibility of the matching problem
        m.available_room = pe.ConstraintList()
        for i in range(self.weeks_begin,self.weeks_end+1):
            for j in range(self.days):
                times = self.split_timeslots.get('week '+str(i)).get('day '+str(j))
                for t in times[1:]:
                    start = times[0]
                    m.available_room.add(sum(sum(m.x[e,l] for l in range(max(start,t-self.events[e].get('duration')-1),t+1) if (e,l) in Index) for e in self.get_events_this_week(i))<= self.rooms_at_t_count[t])


        m.available_room.pprint()
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=False)

        if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
            print ("this is feasible and optimal")
            return "Done",[(e,p) for e,p in Index if pe.value(m.x[e,p]) ==1]
        elif results.solver.termination_condition == TerminationCondition.infeasible:
            print ("do something about it? or exit?")
            return "Not Done"
        else:
            # something else is wrong
            print (str(results.solver))




if __name__ == '__main__':
    # instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    m.split_timeslots

    final = m.CTT()
    final
