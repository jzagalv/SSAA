
from .validators import validate
from .lifecycle import transition

def update_cabinet(cabinet, updates: dict):
    validate(cabinet)
    for key, value in updates.items():
        setattr(cabinet, key, value)
    return cabinet

def advance_state(cabinet, target_state):
    return transition(cabinet, target_state)
