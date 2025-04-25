class FakeState:
    def __init__(self, s, t):
        self.state = s
        self.last_changed = t
        self.attributes = {}
        self.entity_id = "sensor.fake"


class FakeEvent:
    def __init__(self, new_state, time_fired):
        self.data = {"new_state": new_state}
        self.time_fired = time_fired
