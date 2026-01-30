
from .entity import CabinetState

def validate(cabinet):
    if not cabinet.name:
        raise ValueError("Cabinet name is required")
    if not cabinet.location:
        raise ValueError("Cabinet location is required")
    if cabinet.state == CabinetState.LOCKED:
        raise ValueError("Locked cabinet cannot be modified")
    return True
