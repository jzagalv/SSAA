
from .entity import CabinetState

VALID_TRANSITIONS = {
    CabinetState.DRAFT: [CabinetState.DEFINED],
    CabinetState.DEFINED: [CabinetState.VALIDATED],
    CabinetState.VALIDATED: [CabinetState.LOCKED],
    CabinetState.LOCKED: [],
}

def can_transition(current, target):
    return target in VALID_TRANSITIONS.get(current, [])

def transition(cabinet, target_state):
    if not can_transition(cabinet.state, target_state):
        raise ValueError(f"Invalid transition {cabinet.state} -> {target_state}")
    cabinet.state = target_state
    return cabinet
