import datetime
import click


def format_timedelta(timedelta):
    seconds = timedelta.total_seconds()
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return "{:02d}:{:02d}".format(int(hours), int(minutes))


def apply_duration_string(duration_str, base_duration=None):
    """
    Parses a given duration string to a
    :param duration_str: Duration in format [+/-]HH:mm
    :param base_duration: datetime.timedelta
    :return: datetime.timedelta
    """
    if base_duration is None:
        base_duration = datetime.timedelta()

    prefix = ""
    if duration_str.startswith(('+', '-')):
        prefix, duration_str = duration_str[0], duration_str[1:]

    duration_components = duration_str.split(':')
    if len(duration_components) == 1:
        hours_str, minutes_str = duration_components[0], "0"
    elif len(duration_components) == 2:
        hours_str, minutes_str = duration_components
    else:
        raise click.ClickException(
            f"Unexpected duration format. Expected [+/-]HH:mm, instead got {duration_str}"
        )

    try:
        hours, minutes = int(hours_str), int(minutes_str)
    except ValueError:
        raise click.ClickException(
            f"Both hours and minutes components of a duration need to be Integers, "
            f"got {hours_str} and {minutes_str}"
        )

    parsed_duration = datetime.timedelta(hours=hours, minutes=minutes)

    if prefix == "-":
        res_duration = base_duration - parsed_duration
    elif prefix == "+":
        res_duration = base_duration + parsed_duration
    else:
        res_duration = parsed_duration

    return res_duration
