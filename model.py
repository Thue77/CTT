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
        pass

    #Only works when data is for one week
    def events_to_time(self,subset=[]):
        m = pe.ConcreteModel()
        #Only include periods without that are not banned
        P = []
        for week in range(self.weeks_begin,self.weeks_end+1):
            for day,period_list in self.split_periods.get("week "+str(week)).items():
                P.extend([p for p in period_list if all(time not in self.banned for time in self.periods.get(p))])
        E = [key for key in self.events]
        Index = [(e,p) for e in E for p in P]
        #Define variables
        m.x = pe.Var(Index, domain = pe.Binary)

        #Define objective
        m.obj=pe.Objective(expr=1)

        #Hard constraints
        #All events must happen
        m.events_must_happen = pe.Constraint(E,rule = lambda m,e: sum(m.x[e,p] for p in P if (e,p) in Index) ==1 if any((e,p) in Index for p in P) else pe.Constraint.Skip)

        #Precedence constraints
        precedence = [[(e1,e2,p) for p in super(Model,self).get_periods_this_week(int(week[-1]))] for week,l in self.precedence_graph.items() for e1,e2 in l]
        m.precedence = pe.Constraint(range(len(precedence)),rule=lambda m,i: sum(m.x[e1,p]-m.x[e2,p] for j in range(1,len(precedence[i])) for e1,e2,p in precedence[i][:j] if (e1,p) in Index and (e2,p) in Index)>=0)

        #No teacher conflicts
        A = super().conflict_graph_all_weeks(self.teacher_conflict_graph)
        m.teacher_conflict = pe.Constraint(range(len(A)),rule=lambda m,i: sum(m.x[e,p] for e,p in A[i])<=1 if all((e,p) in Index for (e,p) in A[i]) else pe.Constraint.Skip)

        #One event per course per day på student
        # m.one_event_one_day = pe.ConstraintList()
        # for w in range(self.weeks_begin,self.weeks_end+1):
        #     week = "week "+str(w)
        #     for d in range(self.days):
        #         day = "day "+str(d)
        #         for lists in self.student_events.get(week):
        #             m.one_event_one_day.add(sum(m.x[e,p] for e in lists for p in self.split_periods.get(week).get(day) if (e,p) in Index)<=1)

        # def one_event_one_day_rule(m,w,d,i):
        #     week = "week "+str(w)
        #     day = "day "+str(d)
        #     return sum(m.x[e,p] for sets in self.student_events.get(week)[i] for e in sets for p in self.split_periods.get(week).get(day) if (e,p) in Index)<=1
        # m.one_event_one_day = pe.Constraint(range(self.weeks_begin,self.weeks_end+1),range(5),[len(self.student_events.get("week "+str(w))) for w in range(self.weeks_begin,self.weeks_end+1)],rule=one_event_one_day_rule)


        #Ensure feasibility of the matching problem
        m.available_room = pe.ConstraintList()
        for p in self.periods:
            if len([(e,p) in Index for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0 and len([(e,p+1) for e,_ in list(filter(lambda x: x[1] == p,Index))])!=0:
                m.available_room.add(sum(m.x[e,p+1] for e,_ in list(filter(lambda x: x[1] == p+1,Index)))+sum(m.x[e,p] for e,_ in list(filter(lambda x: x[1] == p,Index)))<= self.rooms_at_t_count.get(p))
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=True)
        # m.pprint()
        return [(e,t) for e,t in Index if pe.value(m.x[e,t]) ==1]

    def matching_rooms(self,result):
        m = pe.ConcreteModel()
        print(result)
        E = {i:event for i,event in enumerate(result)}
        periods = set([event[1] for event in E.values()])
        periods = [self.periods.get(p) for p in periods]
        R_list = [(r,period) for r in self.rooms for period in periods if all(p not in self.rooms_busy.get(r) for p in period)]
        R = {i:room for i,room in enumerate(R_list)}
        pairs = [(i,j) for i in range(len(R)-1) for j in range(i+1,len(R)) if abs(super(Model,self).get_dict_key(self.periods,R[i][1])-super(Model,self).get_dict_key(self.periods,R[j][1]))==1 and R[i][0]==R[j][0]]


        A = [(i,j) for i,e in E.items() for j,room in R.items() if self.periods.get(e[1]) == room[1]]

        m.x = pe.Var(A,domain=pe.Binary)
        m.obj = pe.Objective(expr=1)
        #Constraints
        m.room = pe.Constraint(R.keys(),rule=lambda m,r: sum(m.x[e,r] for e in E if (e,r) in A)<=1 if any((e,r) in A for e in E) else pe.Constraint.Skip)
        m.event = pe.Constraint(E.keys(),rule=lambda m,e: sum(m.x[e,r] for r in R if (e,r) in A)==1 if any((e,r) in A for r in R) else pe.Constraint.Skip)
        m.pairs = pe.Constraint(pairs,rule=lambda m,i,j: sum(m.x[e,j] for e,_ in list(filter(lambda x: x[1]==j,A))) + sum(m.x[e,i] for e,_ in list(filter(lambda x: x[1]==i,A)))<=1)
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=True)

        if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
            print ("this is feasible and optimal")
            return "Done",[[(*E.get(i),R.get(j)[0]) for i,j in A if pe.value(m.x[i,j]) ==1]]
        elif results.solver.termination_condition == TerminationCondition.infeasible:

            print ("do something about it? or exit?")
            return "Not Done"
        else:
            # something else is wrong
            print (str(results.solver))



    ## Weekly model. Timeslots and events for one week
    def CTT_week(self,events:dict,timeslots:Dict[str,List[int]],week: int):
        m = pe.ConcreteModel()
        #Only include timeslots that are not banned
        T = [item for key,sublist in timeslots.items() for item in sublist if item not in self.banned_keys]
        E = [key for key in events]
        R = [key for key in self.rooms]
        Index_old = [(e,t,r) for e in E for t in T for r in R]
        #Remove unnecessary indexes
        Index = self.remove_busy_room(self.remove_var_close_to_banned(Index_old))

        #minimize teacher duties per day
        m.x = pe.Var(Index, domain = pe.Binary)
        A = self.teacher_conflict_graph.get("week "+str(week))
        teacher_duties = set([event for t in A for event in t])
        teacher_expr = sum(sum(m.x[e,t,r] for t in times for e in teacher_duties for r in R if (e,t,r) in Index)-1 for times in timeslots.values())


        # #One event per day per course:
        m.one_event_one_day = pe.ConstraintList()
        for course_events in self.courses.values():
            for day in timeslots.values():
                if any((e,t,r) in Index for e in course_events for t in day for r in R):
                    m.one_event_one_day.add(sum(m.x[e,t,r] for e in course_events for t in day for r in R if (e,t,r) in Index)<=1)

        #
        def obj_rule(m):
            A = self.student_conflict_graph.get("week "+str(week))
            starting_index = self.split_timeslots.get("week "+str(week)).get("day 0")[0]
            expr = 0
            for u,v in A:
                for t in T:
                    if any((u,l,r) in Index and (v,l,r) in Index for r in R for l in range(max(starting_index,t-self.events.get(u).get("duration")+1),t+1)):
                        expr += sum(m.x[u,l,r]+m.x[v,l,r] for r in R for l in range(max(starting_index,t-self.events.get(u).get("duration")+1),t+1) if (u,l,r) in Index and (v,l,r) in Index)
            return expr

        m.obj=pe.Objective(rule=obj_rule,sense = pe.minimize)
        # m.obj=pe.Objective(expr = teacher_expr, sense = pe.minimize)
        # m.obj=pe.Objective(expr = 0, sense = pe.minimize)

        #All events must happen
        m.events_must_happen = pe.ConstraintList()
        for e in E:
            m.events_must_happen.add(sum(m.x[e,t,r] for _,t,r in list(filter(lambda x: e == x[0],Index)))==1)

        #No teacher conflicts
        m.teacher_conflict = pe.ConstraintList()
        starting_index = self.split_timeslots.get("week "+str(week)).get("day 0")[0]
        print("Start: ",starting_index)
        for u,v in A:
            for t in T:
                if any((u,l,r) in Index and (v,l,r) in Index for r in R for l in range(max(starting_index,t-self.events.get(u).get("duration")+1),t+1)):
                    m.teacher_conflict.add(sum(m.x[u,l,r]+m.x[v,l,r] for r in R for l in range(max(starting_index,t-self.events.get(u).get("duration")+1),t+1) if (u,l,r) in Index and (v,l,r) in Index) <= 1)


        # #One event per day per course:
        # m.one_event_one_day = pe.ConstraintList()
        # for course_events in self.courses.values():
        #     for day in timeslots.values():
        #         if any((e,t,r) in Index for e in course_events for t in day for r in R):
        #             m.one_event_one_day.add(sum(m.x[e,t,r] for e in course_events for t in day for r in R if (e,t,r) in Index)<=1)

        #Room conflicts
        def room_conf(m,t,r):
            starting_index = self.split_timeslots.get("week "+str(week)).get("day 0")[0]
            if any((e,l,r) in Index for e in E for l in range(max(starting_index,t-self.events.get(e).get("duration")+1),t+1)):
                return sum(m.x[e,l,r] for e in E for l in range(max(starting_index,t-self.events.get(e).get("duration")+1),t+1) if (e,l,r) in Index) <= 1
            else:
                return pe.Constraint.Skip
        m.room_conflicts = pe.Constraint(T,R,rule=room_conf)


        #Precedence constraints
        m.precedence = pe.ConstraintList()
        for u,v in self.precedence_graph.get("week "+str(week)):
            for t in T:
                if any((u,l,r) in Index for l in range(timeslots.get("day 0")[0],t) for r in R):
                    m.precedence.add(sum(m.x[u,l,r]-m.x[v,l,r] for l in range(timeslots.get("day 0")[0],t+1) for r in R if (v,l,r) in Index and (u,l,r) in Index) >= 0)

        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=True)
        print("HERE: ",pe.value(m.obj))
        for e in E:
            print("HERE: ",pe.value(m.x[e,timeslots["day 4"][0],0]))
        return [(e,t,r) for e,t,r in Index if pe.value(m.x[e,t,r]) ==1]
    #Returns list of lists of results for each week
    def CTT(self,weeks: int):
        result_list = []
        for w in range(self.weeks_begin,self.weeks_begin+weeks):
            w=8
            print("Solves for week ",w)
            result_list.append(self.CTT_week(super().get_events_this_week(w),self.split_timeslots.get("week "+str(w)),w))
        return result_list


    #Prints weekly tables for given courses
    def write_time_table_for_course(self,result: List[List[Tuple[Union[int,int]]]],courses: Tuple[str]):
        number_of_weeks = len(result)
        for w,week_result in enumerate(result):
            week = w + self.weeks_begin
            # Set up empty table
            table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
            temp = []
            for room in self.rooms:
                if self.rooms_busy.get(room) not in temp: temp.extend(self.rooms_busy.get(room))
            busy_or_banned = [time for time in temp + self.banned if not (time in temp and self.banned)]
            table.update({"day "+str(j):[["busy"] if {'day':j,'hour':i,'week':week} in busy_or_banned  else [] for i in range(self.hours+1)] for j in range(5)})
            for x in week_result:
                if self.events.get(x[0]).get("id")[0:5] in courses:
                    day = self.periods.get(x[1])[0].get("day")
                    hour = self.periods.get(x[1])[0].get("hour")
                    for i in range(m.period):
                        table["day "+ str(day)][hour+i].append(self.events.get(x[0]).get("id")[0:7])
            print("Week {}\n {}".format(week,pd.DataFrame(table)))

    #Prints time tables for the rooms
    def write_time_table_for_room(self,result: List[List[Tuple[Union[int,int,int]]]],rooms: Tuple[str]):
        number_of_weeks = len(result)
        for w,week_result in enumerate(result):
            week = w + self.weeks_begin
            for room in rooms:
                r = m.get_dict_key(m.rooms,room)
                # Set up empty table indicating slots that are not available
                table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
                busy_or_banned = [time for time in self.rooms_busy.get(r) + self.banned if not (time in self.rooms_busy.get(r) and self.banned)]
                table.update({"day "+str(j):[["busy"] if {'day':j,'hour':i,'week':week} in busy_or_banned  else [] for i in range(self.hours+1)] for j in range(5)})
                for e,p,r in list(filter(lambda x: x[2] == r,week_result)):
                    day = self.periods.get(p)[0].get("day")
                    hour = self.periods.get(p)[0].get("hour")
                    for i in range(self.period):
                        table["day "+ str(day)][hour+i].append(self.events.get(e).get("id")[0:7])
                print("Room {}\n {}".format(room,pd.DataFrame(table)))




if __name__ == '__main__':
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    result = m.events_to_time()
    final = m.matching_rooms(result)
    m.write_time_table_for_course(final[1],[course for course in m.courses])
    m.write_time_table_for_room(final[1],[room for room in m.rooms.values()])
    # %%
