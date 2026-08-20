class PositionState:
    def __init__(self):
        self.previous_positions = {}

    def update_position(self, object_id, center_x, center_y):
        prev = self.previous_positions.get(object_id)
        movement = 0.0
        if prev:
            dx = center_x - prev[0]
            dy = center_y - prev[1]
            movement = (dx ** 2 + dy ** 2) ** 0.5
        self.previous_positions[object_id] = (center_x, center_y)
        return movement

    def clear(self):
        self.previous_positions.clear()
