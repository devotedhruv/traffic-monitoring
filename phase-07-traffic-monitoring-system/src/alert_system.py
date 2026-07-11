from config.settings import SPEED_LIMIT


def check_speed(speed):

    if speed > SPEED_LIMIT:

        return "OVERSPEED"

    else:

        return "NORMAL"