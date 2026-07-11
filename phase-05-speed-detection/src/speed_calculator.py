class SpeedCalculator:


    def __init__(self, distance_meter):

        self.distance_meter = distance_meter



    def calculate_speed(self, time_seconds):

        if time_seconds == 0:
            return 0


        speed_mps = (
            self.distance_meter /
            time_seconds
        )


        speed_kmh = (
            speed_mps * 3.6
        )


        return round(speed_kmh, 2)