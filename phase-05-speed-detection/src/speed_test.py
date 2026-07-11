from speed_calculator import SpeedCalculator


calculator = SpeedCalculator(
    distance_meter=10
)


speed = calculator.calculate_speed(
    time_seconds=1
)


print("==========================")
print("Speed Test")
print("==========================")


print(
    "Speed:",
    speed,
    "km/hr"
)