import pyomo
import pyomo.opt
import pyomo.environ as pe
import pandas as pd

def CTT(events,students,timeslots,consec_events = None):
    m = pe.ConcreteModel()
    times = timeslots.get("not banned")
    E = [(i,t) for i in events for t in times]
    m.x = pe.Var(E, domain = pe.Binary)
    m.obj=pe.Objective(expr=1)
    m.c = pe.ConstraintList()

    #All events must happen
    # m.c.add(sum(m.x[i,t] for i,t in E) == len(events))

    # No more than one event at one time
    for t in times:
        m.c.add(sum(m.x[i,t] for i in events) <= 1)

    # each event must happen exactly 1
    for i in events:
        m.c.add(sum(m.x[i,t] for t in times) == 1)

    # Ensure consecutive events
    if consec_events != None:
        for t_tilde in times:
            for u,v in consec_events:
                m.c.add(sum(m.x[u,t]-m.x[v,t] for t in  range(1,t_tilde+1) if t not in timeslots.get("banned"))>=0)

    solver = pyomo.opt.SolverFactory('glpk')
    results = solver.solve(m,tee=False)
    return {(i,j) : pe.value(m.x[i,j]) for i,j in E if pe.value(m.x[i,j]) ==1 }
    # print(pe.value(m.x[i,t]) for i,t in E)



if __name__ == '__main__':
    events = {"I1":{},"T1":{},"I2":{},"T2":{},"I3":{},"T3":{},"I4":{},"T4":{}}
    consec_events = [("I1","T1"),("I2","T2"),("I3","T3"),("I4","T4")]
    students = None
    timeslots = {"banned":[5],"not banned": [1,2,3,4,6,7,8,9]}
    results = CTT(events,students,timeslots,consec_events)
    print("Results: ",results)
    schedule = {"times":[],"events":[]}
    for r in results:
        schedule["times"].append(r[1])
        schedule["events"].append(r[0])
    print(pd.DataFrame(schedule).sort_values(by="times"))
