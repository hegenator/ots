def format_timedelta(timedelta):
    seconds = timedelta.total_seconds()
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return "{:02d}:{:02d}".format(int(hours), int(minutes))
