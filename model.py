import pyomo
import pyomo.opt
import pyomo.environ as pe
import pandas as pd
import preprocessing as pre
import data
from typing import Dict,List,Tuple,Union
from pyomo.opt import SolverStatus, TerminationCondition
# %%
class Model(pre.preprocess):
    """docstring for Model."""
    def __init__(self,events: Dict[str,dict],slots: List[dict],banned:List[dict],rooms: dict,teachers: Dict[int,List[Dict[str,Union[str,int]]]], students: Dict[int,List[Dict[str,Union[str,int]]]]):
        super().__init__(events,slots,banned,rooms,teachers,students)


    def cut_and_solve(self):
        test = True
        subset_teacher = {"week "+str(w):[] for w in range(self.weeks_begin,self.weeks_end+1)}
        subset_precedence = {"week "+str(w):[] for w in range(self.weeks_begin,self.weeks_end+1)}
        while test:
            result = self.events_to_time(subset_teacher,subset_precedence)
            test = False
            #Cut teacher constraints
            for week,pair_list in self.teacher_conflict_graph.items():
                for pairs in pair_list:
                    if any(abs(list(filter(lambda x:x[0]==e1,result))[0][1]-list(filter(lambda x:x[0]==e2,result))[0][1])<self.period for e1,e2 in pairs):
                        subset_teacher[week].append(pairs)
                        test = True
                        break
            #Cut precedence
            for week,pair_list in self.precedence_graph.items():
                for e1,e2 in pair_list:
                    p1 = list(filter(lambda x:x[0]==e1,result))[0][1]; p2 = list(filter(lambda x:x[0]==e2,result))[0][1];
                    if p1 > p2:
                        subset_precedence[week].extend([(e1,e2)])
                        # test = True
                        break
            # print("Teacher: ",subset_teacher)
            # print("Precedence: ",subset_precedence)
        #Cut precedence constraints:
        # test = True
        # while test:
        #     result = self.events_to_time(self.teacher_conflict_graph,subset)
        #     test = False
        #     for week,pair_list in self.precedence_graph.items():
        #         for e1,e2 in pair_list:
        #             p1 = list(filter(lambda x:x[0]==e1,result))[0][1]; p2 = list(filter(lambda x:x[0]==e2,result))[0][1];
        #             if p1 > p2:
        #                 subset_precedence[week].append((e1,e2))
        #                 test = True
        #                 break
        #     print(subset)
        return self.matching_rooms(result)
            # test = all(len(sublist)==0 for sublist in subset.values())
            # list(filter(lambda x: x[0]==1,[(1,2),(2,2),(3,5)]))[0]
            # m.teacher_conflict_graph
# m.precedence_graph


    #Only works when data is for one week
    def events_to_time(self,subset={},precedence_graph={}):
        m = pe.ConcreteModel()
        #Only include periods without that are not banned
        P = []
        E = []
        Index = []
        for week in range(self.weeks_begin,self.weeks_end+1):
            P.append([])
            for day,period_list in self.split_periods.get("week "+str(week)).items():
                P[-1].extend([p for p in period_list])
            E.append([key for key in self.get_events_this_week(week)])
            Index += [(e,p) for e in E[-1] for p in P[-1]]
        # print(Index)
        # print("E ",E)
        # print("P ",P)

        # E = [key for key in self.events]
        # print(P)
        # Index = [(e,p) for e in E for p in P]
        #Define variables
        m.x = pe.Var(Index, domain = pe.Binary)

        #Soft constraints
        # #minimize teacher duties per day
        # A = self.teacher_conflict_graph.get("week "+str(week))
        # teacher_duties = set([event for t in A for event in t])
        # teacher_expr = sum(sum(m.x[e,t,r] for t in times for e in teacher_duties for r in R if (e,t,r) in Index)-1 for times in timeslots.values())
        # A = super().conflict_graph_all_weeks(self.student_conflict_graph)
        # def student_conflict_rule(m):
        #     expr = 0
        #     for i in range(len(A)):
        #         expr += sum(m.x[e,p] for e,p in A[i])
        #     return expr - len(self.student_conflict_graph)
        #Define objective
        m.obj=pe.Objective(expr=0)
        # m.obj=pe.Objective(rule=student_conflict_rule)

        #Hard constraints
        #All events must happen
        # m.events_must_happen = pe.Constraint(E,rule = lambda m,e: sum(m.x[e,p] for _,p in list(filter(lambda x:x[0]==e))) ==1) #if any((e,p) in Index for p in P) else pe.Constraint.Skip)
        m.events_must_happen = pe.ConstraintList()
        for e in [e for sublist in E for e in sublist]:
            m.events_must_happen.add(sum(m.x[e,p] for _,p in list(filter(lambda x:x[0]==e,Index))) ==1)

        # #Precedence constraints
        m.precedence = pe.ConstraintList()
        # precedence = [[(e1,e2,p) for p in super(Model,self).get_periods_this_week(int(week[-1]))] for week,l in precedence_graph.items() for e1,e2 in l]
        #We do not need to include the last day
        precedence = {week: [[[(e1,e2,p) for p in day_list] for day_list in list(self.split_periods.get(week).values())[:-1]] for e1,e2 in l] for week,l in precedence_graph.items()}
        print(precedence)
        for week_event_list in precedence.values():
            for event_list in week_event_list:
                for i in range(len(event_list)):
                    m.precedence.add(sum(m.x[e1,p]-m.x[e2,p] for e1,e2,p in [item for sublist in event_list[:i+1] for item in sublist])>=0)


        # for precedence_list in precedence:
        #     m.precedence.add()
        # for i in range(len(precedence)):
        #     for j in range(1,len(precedence[i])):
        #         if any((e1,p) in Index and (e2,p) in Index for e1,e2,p in precedence[i][:j]):
        #             m.precedence.add(sum(m.x[e1,p]-m.x[e2,p] for e1,e2,p in precedence[i][:j] if (e1,p) in Index and (e2,p) in Index)>=0)


        # m.precedence = pe.Constraint(range(len(precedence)),rule=lambda m,i: sum(m.x[e1,p]-m.x[e2,p] for j in range(1,len(precedence[i])) for e1,e2,p in precedence[i][:j] if (e1,p) in Index and (e2,p) in Index)>=0)

# m.precedence_graph

        # #No teacher conflicts
        A = super().conflict_graph_all_weeks(subset)
        m.teacher_conflict = pe.Constraint(range(len(A)),rule=lambda m,i: sum(m.x[e,p] for e,p in A[i])<=1 if all((e,p) in Index for (e,p) in A[i]) else pe.Constraint.Skip)

        #One event per course per day på student. This makes precedence constraints easier because we just need to ensure that TE classes happen at least 1 day after the lecture
        m.one_event_one_day = pe.ConstraintList()
        for w in range(self.weeks_begin,self.weeks_end+1):
            week = "week "+str(w)
            for d in range(self.days):
                day = "day "+str(d)
                if len(self.split_periods.get(week).get(day))>0:
                    for lists in self.student_events.get(week):
                        if len(lists)>1:
                            m.one_event_one_day.add(sum(m.x[e,p] for e in lists for p in self.split_periods.get(week).get(day))<=1)


        #Ensure feasibility of the matching problem. Should be improved. Redundant constraints are added
        m.available_room = pe.ConstraintList()
        for p in self.periods:
            if len([(e,p) in Index for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0 and len([(e,p+1) for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0:
                m.available_room.add(sum(m.x[e,p+1] for e,_ in list(filter(lambda x: x[1] == p+1,Index)))+sum(m.x[e,p] for e,_ in list(filter(lambda x: x[1] == p,Index)))<= self.rooms_at_t_count.get(p))


        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=True)
        # m.precedence.pprint()
        return [(e,t) for e,t in Index if pe.value(m.x[e,t]) ==1]

    def matching_rooms(self,result):
        m = pe.ConcreteModel()
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

# m.rooms_busy

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
        P = []
        E = []
        Index = []
        for week in range(self.weeks_begin,self.weeks_end+1):
            P.append([])
            for day,period_list in self.split_periods.get("week "+str(week)).items():
                P[-1].extend([p for p in period_list])
            E.append([key for key in self.get_events_this_week(week)])
            Index += [(e,p) for e in E[-1] for p in P[-1]]

        #Define variables
        m.x = pe.Var(Index, domain = pe.Binary)

        #Define objective
        m.obj=pe.Objective(expr=0)

        #Hard constraints
        #All events must happen
        # m.events_must_happen = pe.Constraint(E,rule = lambda m,e: sum(m.x[e,p] for _,p in list(filter(lambda x:x[0]==e))) ==1) #if any((e,p) in Index for p in P) else pe.Constraint.Skip)
        m.events_must_happen = pe.ConstraintList()
        for e in [e for sublist in E for e in sublist]:
            m.events_must_happen.add(sum(m.x[e,p] for _,p in list(filter(lambda x:x[0]==e,Index))) ==1)

        #One event per course per day på student
        m.one_event_one_day = pe.ConstraintList()
        for w in range(self.weeks_begin,self.weeks_end+1):
            week = "week "+str(w)
            for d in range(self.days):
                day = "day "+str(d)
                if len(self.split_periods.get(week).get(day))>0:
                    for lists in self.student_events.get(week):
                        if len(lists)>1:
                            m.one_event_one_day.add(sum(m.x[e,p] for e in lists for p in self.split_periods.get(week).get(day))<=1)


        #Ensure feasibility of the matching problem. Should be improved. Redundant constraints are added
        m.available_room = pe.ConstraintList()
        for p in self.periods:
            if len([(e,p) in Index for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0 and len([(e,p+1) for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0:
                m.available_room.add(sum(m.x[e,p+1] for e,_ in list(filter(lambda x: x[1] == p+1,Index)))+sum(m.x[e,p] for e,_ in list(filter(lambda x: x[1] == p,Index)))<= self.rooms_at_t_count.get(p))


        m.precedence = pe.ConstraintList()
        m.teacher_conflict = pe.ConstraintList()

        solver = pyomo.opt.SolverFactory('glpk')

        test = True
        counter = 0
        while test:
            results = solver.solve(m,tee=False)
            result = [(e,p) for e,p in Index if pe.value(m.x[e,p]) ==1]
            final = self.matching_rooms(result)
            self.write_time_table_for_course(final[1],[course for course in self.courses],[w for w in range(self.weeks_begin,self.weeks_end+1)])

            subset_teacher = {"week "+str(w):[] for w in range(self.weeks_begin,self.weeks_end+1)}
            subset_precedence = {"week "+str(w):[] for w in range(self.weeks_begin,self.weeks_end+1)}
            test = False
            #Cut teacher
            for week,pair_list in self.teacher_conflict_graph.items():
                for pairs in pair_list:
                    if any(abs(list(filter(lambda x:x[0]==e1,result))[0][1]-list(filter(lambda x:x[0]==e2,result))[0][1])<self.period for e1,e2 in pairs):
                        subset_teacher[week].append(pairs)
                        print("Teacher")
                        print(subset_teacher)
                        test = True
                        break
            #Cut precedence
            for week,pair_list in self.precedence_graph.items():
                for e1,e2 in pair_list:
                    p1 = list(filter(lambda x:x[0]==e1,result))[0][1]; p2 = list(filter(lambda x:x[0]==e2,result))[0][1];
                    if p1 > p2:
                        subset_precedence[week].extend([(e1,e2)])
                        print("Precedence")
                        print(subset_precedence)
                        test = True
                        break

            # precedence = [[(e1,e2,p) for p in super(Model,self).get_periods_this_week(int(week[-1]))] for week,l in subset_precedence.items() for e1,e2 in l]
            # precedence = [[(e1,e2,p) for p in day_list] for week,l in subset_precedence.items() for e1,e2 in l for day_list in self.split_periods.get(week)]
            # for i in range(len(precedence)):
            #     for j in range(1,len(precedence[i])):
            #         if any((e1,p) in Index and (e2,p) in Index for e1,e2,p in precedence[i][:j]):
            #             m.precedence.add(sum(m.x[e1,p]-m.x[e2,p] for e1,e2,p in precedence[i][:j] if (e1,p) in Index and (e2,p) in Index)>=0)

            precedence = {week: [[[(e1,e2,p) for p in day_list] for day_list in list(self.split_periods.get(week).values())[:-1]] for e1,e2 in l] for week,l in subset_precedence.items()}
            for week_event_list in precedence.values():
                for event_list in week_event_list:
                    for i in range(len(event_list)):
                        m.precedence.add(sum(m.x[e1,p]-m.x[e2,p] for e1,e2,p in [item for sublist in event_list[:i+1] for item in sublist])>=0)

            A = super().conflict_graph_all_weeks(subset_teacher)
            for a in A:
                m.teacher_conflict.add(sum(m.x[e,p] for e,p in a)<=1)

            print("Iteration: ",counter)
            counter += 1

        return self.matching_rooms(result)#self.matching_rooms([(e,t) for e,t in Index if pe.value(m.x[e,t]) ==1])

if __name__ == '__main__':
    # instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    # result = m.events_to_time(m.teacher_conflict_graph)
    # final = m.matching_rooms(result)
    # final = m.cut_and_solve()
    final = m.CTT()

    # %%
    m.events[8]
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', -1)
    m.write_time_table_for_course(final[1],[course for course in m.courses],[w for w in range(m.weeks_begin,m.weeks_end+1)])
    m.write_time_table_for_room(final[1],[room for room in m.rooms.values()],[w for w in range(m.weeks_begin,m.weeks_end+1)])

    test = {week: [[[(e1,e2,p) for p in day_list] for day_list in list(m.split_periods.get(week).values())[:-1]] for e1,e2 in l] for week,l in m.precedence_graph.items()}
    test["week 8"][0][0]
