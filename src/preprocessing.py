import data
from typing import Dict,List,Tuple,Union
# %%
class preprocess:
    """docstring for preprocess."""

    def __init__(self,events: Dict[str,dict], slots: List[dict], banned: List[dict], rooms: Dict[str,Dict[str,Union[str,list]]], teachers: Dict[str,List[Dict[str,Union[str,int]]]], students: Dict[str,List[Dict[str,Union[str,int]]]]):
        self.banned = banned #Banned timeslots
        self.slots = slots #All timeslots
        self.teachers = teachers
        self.weeks_end,self.weeks_begin = self.get_weeks() #The starting and ending week
        self.days = self.get_days() #The max number of days per week
        self.hours = self.get_hours() #The max number of hours per day
        self.timeslots = self.get_sorted_times() #dictionary of timeslots
        self.split_timeslots = self.__get_time_week_day() #dict mapping days and weeks to timeslots
        self.rooms,self.rooms_busy = self.get_rooms(rooms)
        self.rooms_at_t,self.rooms_at_t_count = self.get_rooms_at_t()
        self.banned_keys = self.get_banned_keys()
        self.events,self.courses = self.__get_events(events)
        self.R_d_t = self.get_R_d_t() #number of available rooms in (t,t+d-1)
        self.student_events = self.student_events(students)
        self.teacher_conflict_graph = self.get_conflict_graph(teachers)
        self.student_conflict_graph = self.get_conflict_graph(students)
        self.precedence_graph = self.__get_precedence_graph()

    #Returns dict with time as key and a list of available rooms at that time, and length of lists
    def get_rooms_at_t(self):
        R_t = {index:[r for r in self.rooms if t not in self.rooms_busy.get(r)] for index,t in self.timeslots.items()}
        R_t_len = {p:len(room_list) for p,room_list in R_t.items()}
        return R_t,R_t_len


    #Returns a dict with indexes mapping to rooms and a dict with room index mapping to list of busy timeslots
    def get_rooms(self,rooms):
        rooms_indexed = {}
        rooms_busy = {}
        for index,value in enumerate(rooms.values()):
            rooms_indexed[index] = value.get("id")
            rooms_busy[index] = [time for time in value.get("busy")]
        return rooms_indexed,rooms_busy

    #Get the starting and ending weeks
    def get_weeks(self):
        max_week = 0
        min_week = 60
        for key,item in enumerate(self.slots):
            max_week = max((item.get(("week")),max_week))
            min_week = min((item.get(("week")),min_week))
        return max_week,min_week

    #Get the maximum number of days in a week. If there are days 0-4, the result is 5.
    def get_days(self):
        max_day = 0
        for key,item in enumerate(self.slots):
            max_day = max((item.get(("day")),max_day))
        return max_day+1

    #Get the maximum number of hours in a week
    def get_hours(self):
        max_hour = 0
        for key,item in enumerate(self.slots):
            max_hour = max((item.get(("hour")),max_hour))
        return max_hour

    #Sort the timeslots based on hour, day and week respectively
    def get_sorted_times(self):
        temp = {}
        all = self.slots
        for index, time in enumerate(sorted(all,key = lambda k : (k['week'],k['day'],k['hour']))):
            temp[index] = time
        return temp

    #Returns list of keys corresponding to banned timeslots
    def get_banned_keys(self):
        key_list = []
        for key,slot in self.timeslots.items():
            if slot in self.banned:
                key_list += [key]
        return key_list

    # Returns dictionary with timeslots for each day in every week
    def __get_time_week_day(self):
        names_day = ["day " + str(i) for i in range(self.days)]
        names_week = ["week " + str(i) for i in range(self.weeks_begin,self.weeks_end+1)]
        dictionary = {}
        for j,w in enumerate(names_week):
            dictionary[w] = {d: [] for d in names_day}
            for i,d in enumerate(names_day):
                dictionary[w][d] = [key for (key,value) in self.timeslots.items() if value.get("week") == j+self.weeks_begin and value.get("day") == i and value not in self.banned]
        return dictionary


    #Return dict of indexed events and a course dict with all indexes corresponding to each course
    def __get_events(self,events):
        flat_events = {}
        course_dict = {}
        last_index = 0
        for key,item in events.items():
            course_dict[key] = []
            for index,event in enumerate(item):
                event_key = index+last_index
                flat_events[event_key] = event
                course_dict[key].append(event_key)
            last_index += len(item)
        return flat_events,course_dict


    #Use in model as input for weakly model
    def get_times_this_week(self,current_week: int):
        temp = {}
        for key,value in self.timeslots.items():
            if value.get("week") == current_week:
                temp[key] = value
        return temp

    #Returns dict with index as key and events as values for corresponding week
    def get_events_this_week(self,current_week: int):
        temp = {}
        for key,value in self.events.items():
            if value.get("week") == current_week:
                temp[key] = value
        return temp

    #Currently not used. It gets the key based on the value
    def get_dict_key(self,dictionary:dict,val):
        for key,value in dictionary.items():
            if value == val:
                return key

    #Returns dict with week number(str) as key and a List of lists of event conflicts in terms of indexes for that week as value
    def get_conflict_graph(self,participants):
        event_conflict = {"week "+ str(i):[] for i in range(self.weeks_begin,self.weeks_end+1)}
        for participant_list in participants.values():
            for week_dict in participant_list:
                week = "week " + str(week_dict.get('week'))
                events = week_dict.get('events')
                events_keys = [self.get_event_from_id(e) for e in events]
                if events_keys not in event_conflict.get(week) and len(events_keys)>0:
                    event_conflict[week].append(events_keys)
        return event_conflict

    def get_event_from_id(self,id):
        for key,value in self.events.items():
            if value.get("id") == id:
                return key

    def __get_precedence_graph(self):
        precedence_graph = {"week " + str(i):[] for i in range(self.weeks_begin,self.weeks_end+1)}
        for index,event in self.events.items():
            for arc in event.get("in_arcs"):
                index_arc = self.get_event_from_id(arc)
                precedence_graph["week "+str(event.get("week"))].append((index_arc,index))
        return precedence_graph

    def student_events(self,students):
        events = {"week "+str(w):set() for w in range(self.weeks_begin,self.weeks_end+1)}
        for lists in students.values():
            for dicts in lists:
                week = "week "+str(dicts.get('week'))
                courses = set([id[0:5] for id in dicts.get('events')])
                for course in courses:
                    events[week] |= set([frozenset([self.get_event_from_id(id) for id in dicts.get('events') if id[0:5] == course])])
        return {week :[[e for e in subset] for subset in set] for week,set in events.items()}

    #Returns a list of list of time indexes where the lists are sorted by which slots are the least desirable, starting wiht the least desirable
    def get_bad_slots(self):
        #First index in the tuple is the time and the second is the day
        dersirability_list = [[(9,4)],[(7,4),(8,4)],[(0,i) for i in range(0,5)],[(9,i) for i in range(0,4)],[(8,i) for i in range(0,4)]]
        least_desirable_slots = []
        for slots_list in dersirability_list:
            least_desirable_slots.append([t for week,day_dict in self.split_timeslots.items() for day,slots in day_dict.items() for bad_slot in slots_list for t in slots if self.timeslots.get(t).get('hour')==bad_slot[0] and int(day[-1])==bad_slot[1]])
        return least_desirable_slots


    def get_durations(self):
        duration_list = []
        for e in self.events.values():
            if e.get('duration') not in duration_list:
                duration_list += [e.get('duration')]
        return sorted(duration_list)

    #Returns a dict mapping eact (d,t) to a number corresponding to the numberof available rooms in (t,t+d-1)
    def get_R_d_t(self):
        durations = self.get_durations()
        R_d_t = {d:{} for d in durations}
        for d in durations:
            for day_dict in self.split_timeslots.values():
                for day_list in day_dict.values():
                    for t in day_list:
                        R_d_t[d][t] = len([r for r in self.rooms if not any(self.timeslots.get(l) in self.rooms_busy.get(r) for l in range(t,t+d) if l in day_list)])
        return R_d_t





if __name__ == '__main__':
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    # instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    instance = preprocess(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    # %%
    len([r for r in instance.rooms if all({'day':0,'week':6,'hour':i} not in instance.rooms_busy.get(r) for i in range(2))])
    instance.get_durations()
    instance.get_bad_slots()
    sorted([2,1,3,43,5,3,5,21,1])
    list_of_bad_slots = instance.get_bad_slots()
    normalizing_const = sum([i for i in range(1,len(list_of_bad_slots)+1)])
    cost = [i/normalizing_const for i in reversed(range(1,len(list_of_bad_slots)+1))]
