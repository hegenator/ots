import datetime
import click
import shutil

BLOCK_FULL = "█"
BLOCK_MEDIUM_SHADE = "▒"
BLOCK_LIGHT_SHADE = "░"
LEFT_HALF_BLOCK = "▌"
ARROW_DOWN = "↓"


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


def limit_str_length(value, max_len=50):
    max_len = max(max_len, 3)
    value = str(value) if value is not None else ""
    if len(value) > max_len:
        return f"{value[:max_len - 3]}..."
    return value


def float_hours_to_duration_string(hours):
    duration = datetime.timedelta(hours=hours)
    return format_timedelta(duration)


def get_terminal_width():
    terminal_size = shutil.get_terminal_size((80, 40))
    return terminal_size.columns
