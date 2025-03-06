from datetime import timedelta

def parse_custom_time(time_str):
    try:
        if not isinstance(time_str, str) or ":" not in time_str:
            return None
        hours, minutes = map(int, time_str.split(':'))
        return timedelta(hours=hours, minutes=minutes)
    except (ValueError, AttributeError):
        return None

def format_custom_time(time_delta):
    total_seconds = int(time_delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}:{minutes:02}"