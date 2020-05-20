import pyomo
import pyomo.opt
import pyomo.environ as pe
import pandas as pd
import math
import preprocessing as pre
import data
from typing import Dict,List,Tuple,Union
from pyomo.opt import SolverStatus, TerminationCondition

# %%

class Model(pre.preprocess):
    """docstring for Model."""
    def __init__(self,events: Dict[str,dict],slots: List[dict],banned:List[dict],rooms: dict,teachers: Dict[int,List[Dict[str,Union[str,int]]]], students: Dict[int,List[Dict[str,Union[str,int]]]]):
        super().__init__(events,slots,banned,rooms,teachers,students)


    def split_result_by_duration(self,result):
        durations = set([self.events[e].get('duration') for e,_ in result])
        return {d:[(e,t) for e,t in result if self.events[e].get('duration') == d] for d in durations}

    def remove_var_close_to_banned(self,Index:List[Tuple[int,int,int]]):
        Index_old = Index.copy()
        Index_new = Index.copy()
        for x in Index_old:
            duration = self.events.get(x[0]).get("duration")
            day = self.timeslots.get(x[1]).get("day")
            week = self.timeslots.get(x[1]).get("week")
            last_key = self.split_timeslots.get('week '+str(week)).get('day '+str(day))[-1]
            if last_key-x[1]<duration-1:
                    Index_new.remove(x)
            else:
                for t_banned in self.banned_keys:
                    if  day == self.timeslots.get(t_banned).get("day") and week == self.timeslots.get(t_banned).get("week") and t_banned-x[1] < duration and t_banned>x[1]:
                        Index_new.remove(x)
                        break
        return Index_new


    def matching_rooms(self,result):
        m = pe.ConcreteModel()
        E = {i:event for i,event in enumerate(result)}
        R = {i:x for i,x in enumerate(set([(r,t,self.events[e].get('duration')) for e,t in result for r in self.rooms if not any(self.timeslots.get(l) in self.rooms_busy.get(r) for l in range(t,t+self.events[e].get('duration')))]))}
        I = [(i,j) for i,e in E.items() for j,r in R.items() if e[1]==r[1] and self.events[e[0]].get('duration') == r[2]]
        #Find overlapping rooms
        A_bar = []
        for r in self.rooms:
            list_for_r = sorted(list(filter(lambda x:x[1][0]==r,R.items())),key=lambda x: x[1][1])
            Added = False
            temp_1 = set()
            for i,temp in enumerate(list_for_r[:-1]):
                index = temp[0]
                room = temp[1]
                t = room[1]
                duration = room[2]
                if list_for_r[i+1][1][1]-t<duration:
                    temp_1 |= {index,list_for_r[i+1][0]}
                elif len(temp_1)>0:
                    A_bar.append(temp_1)
                    temp_1 = set()
            if len(temp_1)>0:
                A_bar.append(temp_1)
        U_A = [item for subset in A_bar for item in subset]
        m.x = pe.Var(I,domain=pe.Binary)
        m.obj = pe.Objective(expr=0)
        #Constraints
        #Cuts rooms.
        m.room = pe.Constraint([r for r in R.keys() if r not in U_A],rule=lambda m,r: sum(m.x[e,r] for e,_ in list(filter(lambda x: x[1]==r,I)))<=1)
        #Cuts for events
        m.event = pe.Constraint(E.keys(),rule=lambda m,e: sum(m.x[e,r] for _,r in list(filter(lambda x:x[0]==e,I)))==1)
        #Only one edge for each pair of (r,p) vertices that have overlapping periods
        m.overlap = pe.ConstraintList()
        for A in A_bar:
            m.overlap.add(sum(m.x[e,r] for r in A for e,_ in list(filter(lambda x: x[1]==r,I)))<=1)
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=False)

        if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
            print ("this is feasible and optimal")
            return "Done",[[(*E.get(i),R.get(j)[0]) for i,j in I if pe.value(m.x[i,j]) ==1 and self.timeslots[E.get(i)[1]].get('week')==w] for w in range(self.weeks_begin,self.weeks_end+1)]
        elif results.solver.termination_condition == TerminationCondition.infeasible:
            print ("Matching is not feasible")
            return "Not Done"
        else:
            # something else is wrong
            print (str(results.solver))


    #Prints weekly tables for given courses
    def write_time_table_for_course(self,result: List[List[Tuple[Union[int,int]]]],courses: Tuple[str],week_numbers: List[int]):
        number_of_weeks = len(result)
        df_dict = {} #List of data frames
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
                        day = self.timeslots.get(x[1]).get("day")
                        hour = self.timeslots.get(x[1]).get("hour")
                        for i in range(self.events.get(x[0]).get('duration')):
                            table["day "+ str(day)][hour+i].append(self.events.get(x[0]).get("id")[0:7])
                df_dict["Week "+str(week)] = pd.DataFrame(table)
        return df_dict


    #Prints time tables for the rooms
    def write_time_table_for_room(self,result: List[List[Tuple[Union[int,int,int]]]],rooms: Tuple[str],week_numbers:[List[int]]):
        number_of_weeks = len(result)
        df_dict = {"Week "+str(w):{} for w in range(self.weeks_begin,self.weeks_end+1)}
        for w,week_result in enumerate(result):
            week = w + self.weeks_begin
            if week in week_numbers:
                for room in rooms:
                    r = self.get_dict_key(self.rooms,room)
                    # Set up empty table indicating slots that are not available
                    table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
                    busy_or_banned = [time for time in self.rooms_busy.get(r) + self.banned if not (time in self.rooms_busy.get(r) and time in self.banned)]
                    table.update({"day "+str(j):[["busy"] if {'day':j,'hour':i,'week':week} in busy_or_banned  else [] for i in range(self.hours+1)] for j in range(5)})
                    for e,p,r in list(filter(lambda x: x[2] == r,week_result)):
                        day = self.timeslots.get(p).get("day")
                        hour = self.timeslots.get(p).get("hour")
                        for i in range(self.events.get(e).get('duration')):
                            table["day "+ str(day)][hour+i].append(self.events.get(e).get("id")[0:7])
                    # print("Week: {}, Room: {}\n {}".format(week,room,pd.DataFrame(table)))
                    df_dict["Week "+str(week)]["Room " + room] = pd.DataFrame(table)
        return df_dict


    def CTT(self):
        m = pe.ConcreteModel()
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
        #Index for auxillary variables:
        temp = [(c,t) for week,day_dict in self.split_timeslots.items() for c in self.student_conflict_graph.get(week) for t in [t for sublist in day_dict.values() for t in sublist]]
        I_student = {i:item for i,item in enumerate(temp)}
        I_teacher = {i:item for i,item in enumerate([(c,day,week) for week,C_bar in self.teacher_conflict_graph.items() for c in C_bar for day,day_list in self.split_timeslots.get(week).items() if len(day_list)>0])}

        #Define variables
        m.x = pe.Var(Index, domain = pe.Binary)
        m.w = pe.Var(I_student.keys(),domain = pe.NonNegativeIntegers) #student conflicts
        m.y = pe.Var(I_teacher.keys(),domain = pe.NonNegativeIntegers) #Teacher duties each day


        #Soft constraints
        m.student_overlap = pe.ConstraintList()
        for i,c_t in I_student.items():
            C = c_t[0]; t = c_t[1];
            week = 'week '+ str(self.timeslots.get(t).get('week')); day = 'day '+ str(self.timeslots.get(t).get('day'))
            start = self.split_timeslots.get(week).get(day)[0]
            if any((e,l) in Index for e in C for l in range(max(start,t-self.events.get(e).get('duration')+1),t+1)):
                total_event = sum([self.events.get(e).get('duration') for e in C])
                m.student_overlap.add(sum(m.x[e,l]for e in C for l in range(max(start,t-self.events.get(e).get('duration')+1),t+1) if (e,l) in Index)-1<=m.w[i])

        m.teacher_duties = pe.ConstraintList()
        for i,c_t in I_teacher.items():
            C = c_t[0]; day = c_t[1]; week = c_t[2];
            m.teacher_duties.add(sum(m.x[e,t] for e in C for t in self.split_timeslots.get(week).get(day) if (e,t) in Index)-1 <= m.y[i])


        #Cost for bad slots:
        list_of_bad_slots = self.get_bad_slots()
        normalizing_const = sum([i for i in range(1,len(list_of_bad_slots)+1)])
        cost = [i/normalizing_const for i in reversed(range(1,len(list_of_bad_slots)+1))]


        #Define objective
        m.obj=pe.Objective(expr=0.50*sum(m.w[i] for i in I_student)+0.3*sum(m.y[i] for i in I_teacher) + 0.2*sum(c*sum(m.x[e,t] for t in bad_slots for e,_ in list(filter(lambda x:x[1]==t,Index))) for c,bad_slots in zip(cost,list_of_bad_slots)))
        # m.obj = pe.Objective(expr=0)

        #Hard constraints
        #All events must happen
        m.events_must_happen = pe.ConstraintList()
        for e in [e for sublist in E for e in sublist]:
            m.events_must_happen.add(sum(m.x[e,t] for _,t in list(filter(lambda x:x[0]==e,Index))) == 1)

        #One event per course per day på student
        m.one_event_one_day = pe.ConstraintList()
        for w in range(self.weeks_begin,self.weeks_end+1):
            week = "week "+str(w)
            W_s = self.split_timeslots.get(week)
            S_bar = self.student_events.get(week)
            for S in S_bar:
                for D in W_s.values():
                    if any((e,t) for e in S for _,t in list(filter(lambda x: x[0]==e and x[1] in D,Index))):
                        m.one_event_one_day.add(sum(m.x[e,t] for e in S for _,t in list(filter(lambda x: x[0]==e and x[1] in D,Index)))<=1)

        m.precedence = pe.ConstraintList()
        precedence = {week: [[[(e1,e2,t) for t in day_list] for day_list in list(self.split_timeslots.get(week).values())[:-1]] for e1,e2 in l] for week,l in self.precedence_graph.items()}
        for week_event_list in precedence.values():
            for event_list in week_event_list:
                for i in range(len(event_list)):
                    if any((e1,t) in Index and (e2,t) in Index for e1,e2,t in [item for sublist in event_list[:i+1] for item in sublist]):
                        m.precedence.add((sum(m.x[e1,t] for e1,e2,t in [item for sublist in event_list[:i+1] for item in sublist] if (e1,t) in Index)-sum(m.x[e2,t] for e1,e2,t in [item for sublist in event_list[:i+1] for item in sublist] if (e2,t) in Index))>=0)


        #Teacher-conflict constraints:
        m.teacher_conflict = pe.ConstraintList()


        #Ensure feasibility of the matching problem
        m.available_room = pe.ConstraintList()
        #Ensure that no event changes room in its duration
        m.same_room = pe.ConstraintList()

        solver = pyomo.opt.SolverFactory('glpk')
        test = True
        count = 0
        while test:
            test = False
            results = solver.solve(m,tee=False)
            result = [(e,t) for e,t in Index if pe.value(m.x[e,t]) ==1]


            #Find teacher and room conflicts
            subset_room = {} #Dict of weeks and days for which there at some time is too many rooms
            subset_teacher = {"week "+str(w):[] for w in range(self.weeks_begin,self.weeks_end+1)} #Dict[week,List[list]] every list in List constains a set of events that are not allowed to overlap
            #Cut teacher constraints
            for week,conflict_list in self.teacher_conflict_graph.items():
                for event_list in conflict_list:
                    times = sorted([(e,t) for e in event_list for _,t in list(filter(lambda x:x[0]==e,result))],key=lambda x:x[1])
                    if any(x[1]+self.events[x[0]].get('duration')-1>=t2 for i,x in enumerate(times[:-1]) for e2,t2 in times[i+1:]):
                        subset_teacher[week].append([e for e,t in times])
                        test = True
                        break
            #Cuts for rooms
            counts = {t: 0 for t in self.timeslots}
            for e,t in result:
                for t_prime in range(t,t+self.events[e].get('duration')):
                    counts[t_prime] += 1
            for t,count in counts.items():
                week = 'week '+str(self.timeslots.get(t).get('week'))
                if subset_room.get(t)==None and count>self.rooms_at_t_count.get(t):
                    day = 'day '+str(self.timeslots.get(t).get('day'))
                    subset_room[week] = day
                    test = True

            #Cuts for same room
            t_list = set([t for _,t in result])
            result_by_d = self.split_result_by_duration(result)
            subset_same_room = [] if test else [(d,t) for d,event_list in result_by_d.items() for t in t_list if len(list(filter(lambda x: x[1]==t,event_list)))>self.R_d_t[d][t]]
            if len(subset_same_room)>0:
                test = True

            #Add Cuts
            #Teacher
            for week,C_bar in subset_teacher.items():
                W_C =  self.split_timeslots.get(week).values()
                for C in C_bar:
                    for D in W_C:
                        for t in D:
                            start = D[0]
                            if any((e,l) in Index for e in C for l in range(max(start,t-self.events.get(e).get('duration')+1),t+1)):
                                m.teacher_conflict.add(sum(sum(m.x[e,l] for l in range(max(start,t-self.events.get(e).get('duration')+1),t+1) if (e,l) in Index) for e in C)<=1)

            #Rooms
            for week,day in subset_room.items():
                times = self.split_timeslots.get(week).get(day)
                for t in times:
                    start = times[0]
                    if sum([(e,l) in Index for e in self.get_events_this_week(int(week[5:])) for l in range(max(start,t-self.events[e].get('duration')+1),t+1)])>self.rooms_at_t_count[t]:
                        m.available_room.add(sum(m.x[e,l] for e in self.get_events_this_week(int(week[5:])) for l in range(max(start,t-self.events[e].get('duration')+1),t+1) if (e,l) in Index)<= self.rooms_at_t_count[t])

            #Same room
            for d,t in subset_same_room:
                m.same_room.add(sum(m.x[e,t] for e,_ in list(filter(lambda x: self.events.get(x[0]).get('duration')==d and x[1]==t,Index)))<= self.R_d_t[d][t])

        if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
            print ("this is feasible and optimal")
            print("Objective: ",pe.value(m.obj))
            print("conflicts: ",sum(pe.value(m.w[i]) for i in I_student))
            print("Extra teacher duties: ",sum(pe.value(m.y[i]) for i in I_teacher))
            print("Number of events: ",sum(pe.value(m.x[e,t]) for e,t in Index))
            print("Number of bad slots: ",[sum(pe.value(m.x[e,t]) for t in bad_slots for e,_ in list(filter(lambda x:x[1]==t,Index))) for bad_slots in list_of_bad_slots])
            return self.matching_rooms(result)
        elif results.solver.termination_condition == TerminationCondition.infeasible:
            print ("Infeasible")
            # return "Not Done"
        else:
            # something else is wrong
            print (str(results.solver))





if __name__ == '__main__':
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    # instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    m.events[1]
    final = m.CTT()
    # %%
    week_dict = m.write_time_table_for_course(final[1],[course for course in m.courses],[w for w in range(m.weeks_begin,m.weeks_end+1)])
    room_dict = m.write_time_table_for_room(final[1],[r for r in m.rooms.values()],[w for w in range(m.weeks_begin,m.weeks_end+1)])
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    print(week_dict.get("Week 18").to_latex(index = False))
    room_dict['Week 18']