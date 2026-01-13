class Team:
    def __init__(self, name, attributes=None):
        self.name = name
        self.attributes = attributes if attributes else {}

    def __repr__(self):
        return f"Team(name={self.name}, attributes={self.attributes})"


class Court:
    def __init__(self, name, start_time, end_time=None):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time  # Optional end time for court availability
        self.matches = []  # Add this line

    def __repr__(self):
        return f"Court(name={self.name}, start_time={self.start_time}, end_time={self.end_time})"


class Constraint:
    def __init__(self, type, value):
        self.type = type
        self.value = value

    def __repr__(self):
        return f"Constraint(type={self.type}, value={self.value})"