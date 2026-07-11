import time


class SpeedManager:


    def __init__(self):

        self.vehicle_time = {}



    def calculate(self, vehicle_id):


        current = time.time()


        if vehicle_id not in self.vehicle_time:

            self.vehicle_time[vehicle_id] = current

            return 0



        start = self.vehicle_time[vehicle_id]


        distance = 10


        time_taken = current - start


        if time_taken == 0:
            return 0


        speed = (distance / time_taken) * 3.6


        return round(speed,2)