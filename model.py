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
    def CTT_week(self,events:dict,timeslots:dict):
        m = pe.ConcreteModel()
        T = [item for key,sublist in timeslots.items() for item in sublist if self.timeslots.get(item) not in self.banned]
        # print(self.banned)
        E = [key for key in events]
        R = [key for key in self.rooms]
        Index = [(e,t,r) for e in E for t in T for r in R]
        for e,t,r in Index:
            duration = self.events.get(e).get("duration")
            for t_banned in self.banned_keys:
                if self.timeslots.get(t).get("day") == self.timeslots.get(t_banned).get("day") and t_banned-t >= duration:
                    Index.remove((e,t,r))
                    break
        m.x = pe.Var(Index, domain = pe.Binary)
        m.obj=pe.Objective(expr=1)
        #All events must happen
        m.events_must_happen = pe.ConstraintList()
        for e in E:
            m.events_must_happen.add(sum(m.x[e,t,r] for _,t,r in Index)==1)
        #Cannot start too close to a banned timeslot
        # m.no_banned_timeslots = pe.ConstraintList()
        # for e in E:
        #     duration = self.events.get(e).get("duration")
        #     for t in self.banned_keys:
        #         m.no_banned_timeslots.add(sum(m.x[e,l,r] for r in R for l in range(t-duration+1,t) if (e,l,r) in Index)==0)

        #
        # # each event must happen exactly 1
        # for i in events:
        #     m.c.add(sum(m.x[i,t] for t in times) == 1)
        #
        # # Ensure consecutive events
        # if consec_events != None:
        #     for t_tilde in times:
        #         for u,v in consec_events:
        #             m.c.add(sum(m.x[u,t]-m.x[v,t] for t in  range(1,t_tilde+1) if t not in timeslots.get("banned"))>=0)
        solver = pyomo.opt.SolverFactory('glpk')
        results = solver.solve(m,tee=False)
        m.pprint()
        return [(e,t,r) for e,t,r in Index if pe.value(m.x[e,t,r]) ==1]
        # print(pe.value(m.x[i,t]) for i,t in E)
    #Returns list of lists of results for each week
    def CTT(self,weeks: int):
        result_list = [] #
        for w in range(self.weeks_begin,self.weeks_begin+weeks):
            result_list.append(self.CTT_week(super().get_events_this_week(w),self.set_of_weeks.get("week "+str(w))))
        return result_list

    #Prints weekly tables for given courses
    def write_time_table_for_course(self,result: List[List[Tuple[Union[int,int,int]]]],courses: Tuple[str]):
        result.sort(key = lambda k:k[1])
        number_of_weeks = len(result)
        for week_result in result:
            # Set up empty table
            table = {"Time":[(8+i,9+i) for i in range(12)]}
            table.update({"day "+str(j):[[] for i in range(11+1)] for j in range(5)})
            for e,t,r in week_result:
                if self.events.get(e).get("id")[0:5] in courses:
                    day = self.timeslots.get(t).get("day")
                    hour = self.timeslots.get(t).get("hour")
                    table["day "+ str(day)][hour].append(self.events.get(e).get("id")[0:7])
            print(pd.DataFrame(table))




if __name__ == '__main__':
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    m = Model(instance_data.events,instance_data.slots,instance_data.banned,{1:{'size':20}},instance_data.teachers)
    result = m.CTT(1)
    m.write_time_table_for_course(result,["DM871"])


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
