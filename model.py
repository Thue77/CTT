import pyomo
import pyomo.opt
import pyomo.environ as pe
import pandas as pd
import preprocessing as pre
import data
from typing import Dict,List,Tuple,Union
# %%
class Model(pre.preprocess):
    """docstring for Model."""
    def __init__(self,events: Dict[str,dict],slots: List[dict],banned:List[dict],rooms: dict,teachers: Dict[int,List[Dict[str,Union[str,int]]]]):
        super().__init__(events,slots,banned,rooms,teachers)

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

        m.x = pe.Var(Index, domain = pe.Binary)
        m.obj=pe.Objective(expr=1)
        #All events must happen
        m.events_must_happen = pe.ConstraintList()
        for e in E:
            m.events_must_happen.add(sum(m.x[e,t,r] for _,t,r in list(filter(lambda x: e == x[0],Index)))==1)

        #No teacher conflicts
        m.teacher_conflict = pe.ConstraintList()
        A = self.teacher_conflict_graph.get("week "+str(week))
        for u in A:
            for v in A:
                if u!=v:
                    for t in T:
                        if any((u,l,r) in Index for r in R for l in range(max(0,t-self.events.get(u).get("duration")+1),t+1)) or any((v,l,r) in Index for r in R for l in range(max(0,t-self.events.get(u).get("duration")+1),t+1)):
                            m.teacher_conflict.add(sum(m.x[u,l,r]+m.x[v,l,r] for r in R for l in range(max(0,t-self.events.get(u).get("duration")+1),t+1) if (u,l,r) in Index and (v,l,r) in Index) <= 1)

        #One event per day per course:
        m.one_event_one_day = pe.ConstraintList()
        for course_events in self.courses.values():
            for day in timeslots.values():
                if any((e,t,r) in Index for e in course_events for t in day for r in R):
                    m.one_event_one_day.add(sum(m.x[e,t,r] for e in course_events for t in day for r in R if (e,t,r) in Index)<=1)

        #Precedence constraints
        m.precedence = pe.ConstraintList()
        for u,v in self.precedence_graph.get("week "+str(week)):
            for t in T:
                if any((u,l,r) in Index for l in range(timeslots.get("day 0")[0],t) for r in R):
                    m.precedence.add(sum(m.x[u,l,r]-m.x[v,l,r] for l in range(timeslots.get("day 0")[0],t+1) for r in R if (v,l,r) in Index and (u,l,r) in Index) >= 0)

        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=True)
        return [(e,t,r) for e,t,r in Index if pe.value(m.x[e,t,r]) ==1]
    #Returns list of lists of results for each week
    def CTT(self,weeks: int):
        result_list = []
        for w in range(self.weeks_begin,self.weeks_begin+weeks):
            # w=9
            print("Solves for week ",w)
            result_list.append(self.CTT_week(super().get_events_this_week(w),self.set_of_weeks.get("week "+str(w)),w))
        return result_list

    def remove_var_close_to_banned(self,Index:List[Tuple[int,int,int]]):
        Index_old = Index.copy()
        Index_new = Index.copy()
        for e,t,r in Index_old:
            duration = self.events.get(e).get("duration")
            for t_banned in self.banned_keys:
                if self.timeslots.get(t).get("day") == self.timeslots.get(t_banned).get("day") and abs(t_banned-t) < duration:
                    Index_new.remove((e,t,r))
                    break
        return Index_new

    def remove_busy_room(self, Index: List[Tuple[int,int,int]]):
        Index_old = Index.copy()
        Index_new = Index.copy()
        for e,t,r in Index_old:
            if t in self.rooms_busy.get(r):
                Index_new.remove((e,t,r))
        return Index_new

    #Prints weekly tables for given courses
    def write_time_table_for_course(self,result: List[List[Tuple[Union[int,int,int]]]],courses: Tuple[str]):
        number_of_weeks = len(result)
        for week,week_result in enumerate(result):
            # Set up empty table
            table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
            table.update({"day "+str(j):[[] for i in range(self.hours+1)] for j in range(5)})
            for e,t,r in week_result:
                if self.events.get(e).get("id")[0:5] in courses:
                    day = self.timeslots.get(t).get("day")
                    hour = self.timeslots.get(t).get("hour")
                    table["day "+ str(day)][hour].append(self.events.get(e).get("id")[0:7])
            print("Week {}\n {}".format(week+self.weeks_begin,pd.DataFrame(table)))

    #Prints time tables for the rooms
    def write_time_table_for_room(self,result: List[List[Tuple[Union[int,int,int]]]],rooms: Tuple[str]):
        number_of_weeks = len(result)
        for week,week_result in enumerate(result):
            for room in rooms:
                # Set up empty table
                table = {"Time":[(8+i,9+i) for i in range(self.hours+1)]}
                table.update({"day "+str(j):[[] for i in range(self.hours+1)] for j in range(5)})
                for e,t,r in week_result:
                    if self.rooms.get(r) == room:
                        day = self.timeslots.get(t).get("day")
                        hour = self.timeslots.get(t).get("hour")
                        table["day "+ str(day)][hour].append(self.events.get(e).get("id")[0:7])
                print("Room {}\n {}".format(room,pd.DataFrame(table)))




if __name__ == '__main__':
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers)
    result = m.CTT(1)
    m.write_time_table_for_course(result,[course for course in m.courses])
    m.write_time_table_for_room(result,[room for room in m.rooms.values()])
    # %%
    print(test.set_of_weeks)
    # test.timeslots
    results = CTT(events,timeslots)
    print("Results: ",results)
    schedule = {"times":[],"events":[]}
    for r in results:
        schedule["times"].append(r[1])
        schedule["events"].append(r[0])
    print(pd.DataFrame(schedule).sort_values(by="times"))
