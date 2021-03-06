import data
from typing import Dict,List,Tuple,Union
# %%
class preprocess:
    """docstring for preprocess."""

    def __init__(self,events: Dict[str,dict], slots: List[dict], banned: List[dict], rooms: Dict[str,Dict[str,Union[str,list]]], teachers: Dict[str,List[Dict[str,Union[str,int]]]], students: Dict[str,List[Dict[str,Union[str,int]]]]):
        self.banned = banned #Banned timeslots
        self.slots = slots #All timeslots
        self.teachers = teachers
        self.period = 2
        self.weeks_end,self.weeks_begin = self.get_weeks() #The starting and ending week
        self.days = self.get_days() #The max number of days per week
        self.hours = self.get_hours() #The max number of hours per day
        self.timeslots = self.get_sorted_times() #dictionary of timeslots
        self.split_timeslots = self.__get_time_week_day() #dict mapping days and weeks to timeslots
        self.split_periods = self.__get_sorted_periods()
        self.rooms,self.rooms_busy = self.get_rooms(rooms)
        self.rooms_at_t,self.rooms_at_t_count = self.get_rooms_at_t()
        self.banned_keys = self.get_banned_keys()
        self.events,self.courses = self.__get_events(events)
        self.teacher_conflict_graph = self.get_event_conflict(teachers)
        self.student_conflict_graph = self.get_event_conflict(students)
        self.precedence_graph = self.__get_precedence_graph()

    #Returns dict with time as key and a list of available rooms at that time, and length of lists
    def get_rooms_at_t(self):
        R_t = {t:[r for r in self.rooms if t not in self.rooms_busy.get(r)] for t in self.timeslots}
        R_t_len = {t:len(room_list) for t,room_list in R_t.items()}
        return R_t,R_t_len

    #Returns a dict with indexes mapping to rooms and a dict with room index mapping to list of busy timeslots
    def get_rooms(self,rooms):
        rooms_indexed = {}
        rooms_busy = {}
        for index,value in enumerate(rooms.values()):
            rooms_indexed[index] = value.get("id")
            rooms_busy[index] = [self.get_dict_key(self.timeslots,time) for time in value.get("busy")]
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


    def __get_sorted_periods(self):
        split_periods = {week:{day:self.__get_duration_sized_tuple(list_pair) for day,list_pair in day_dict.items()} for week,day_dict in self.split_timeslots.items()}
        return split_periods

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
                dictionary[w][d] = [key for (key,value) in self.timeslots.items() if value.get("week") == j+self.weeks_begin and value.get("day") == i]
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
        # print("Something went wrong with the _get_dict_key() method for value: {}".format(val))
    #Get all elements in the list in duration sized tuples
    def __get_duration_sized_tuple(self,list_to_subset):
        return [[p for p in list_to_subset[i:i+self.period]] for i in range(0,len(list_to_subset),self.period)]



    #Get all elements in the list paired
    def __all_pairings(self,list_to_pair: List):
        list_of_pairs = [(p1,p2) for index,p1 in enumerate(list_to_pair) for p2 in list_to_pair[index+1:]]
        # list_of_pairs = []
        # for index,p1 in enumerate(list_to_pair):
        #     for p2 in list_to_pair[index+1:]:
        #         list_of_pairs.append((p1,p2))
        return list_of_pairs


    '''Could work for both students and teacher'''
    #Returns dict with week number as key and a list of event conflicts in terms of indexes for that week as value
    def get_event_conflict(self,participants):
        course_conflict = self.__get_course_conflict(participants)
        event_conflict = {"week "+ str(i):[] for i in range(self.weeks_begin,self.weeks_end+1)}
        for week in range(self.weeks_begin,self.weeks_end+1):
            current_week = "week "+str(week)
            for index,event_dict in self.get_events_this_week(week).items():
                if event_dict.get("id")[0:5] in course_conflict.get(current_week):
                    event_conflict[current_week].append(index)

        for week_number,conflict_list in event_conflict.items():
            event_conflict[week_number] = self.__all_pairings(conflict_list)
        return event_conflict

    #Returns dict week number as key and a list of course conflicts for that week as value
    def __get_course_conflict(self,participants):
        course_conflict = {"week "+ str(i):[] for i in range(self.weeks_begin,self.weeks_end+1)}
        for event_list in participants.values():
            for event_dict in event_list:
                week = event_dict.get("week")
                for id in event_dict.get("events"):
                    if id[0:5] not in course_conflict.get("week "+str(week)):
                        course_conflict.get("week "+str(week)).append(id[0:5])
        return course_conflict

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



if __name__ == '__main__':
    # instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\Material\\CTT\\data\\small")
    instance_data = data.Data("C:\\Users\\thom1\\OneDrive\\SDU\\8. semester\\Linear and integer programming\\Part 2\\01Project\\data_baby_ex")
    instance = preprocess(instance_data.events,instance_data.slots,instance_data.banned,instance_data.rooms,instance_data.teachers,instance_data.students)
    # %%
    instance.split_timeslots.get('week 8').get("day 1")
    instance.split_periods
