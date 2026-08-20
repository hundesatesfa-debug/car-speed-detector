class SpeedState:
    def __init__(self):
        self.start_frames = {}
        self.speeds = {}
        self.violations_set = {}

    def clear(self):
        self.start_frames.clear()
        self.speeds.clear()
        self.violations_set.clear()


def update_speed(state, object_id, frame_number, fps, distance_meters):
    if object_id not in state.start_frames:
        return None

    frames_taken = frame_number - state.start_frames[object_id]
    time_seconds = frames_taken / fps

    if time_seconds <= 0:
        return None

    speed_mps = distance_meters / time_seconds
    speed_kmh = speed_mps * 3.6
    state.speeds[object_id] = speed_kmh
    return speed_kmh


def get_speed(state, object_id):
    return state.speeds.get(object_id)


def mark_violation(state, object_id):
    state.violations_set[object_id] = True


def is_violation_recorded(state, object_id):
    return object_id in state.violations_set


def check_line_crossing(state, object_id, center_y, line_y, frame_number):
    if center_y >= line_y and object_id not in state.start_frames:
        state.start_frames[object_id] = frame_number
        return True
    return False


def check_speed_line(state, object_id, center_y, line_b_y, frame_number, fps, distance_meters):
    if (
        center_y >= line_b_y
        and object_id in state.start_frames
        and object_id not in state.speeds
    ):
        speed = update_speed(state, object_id, frame_number, fps, distance_meters)
        return speed
    return None
