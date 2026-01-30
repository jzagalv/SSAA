
from dataclasses import dataclass, field
from enum import Enum
import uuid

class CabinetState(Enum):
    DRAFT = "DRAFT"
    DEFINED = "DEFINED"
    VALIDATED = "VALIDATED"
    LOCKED = "LOCKED"

@dataclass
class Cabinet:
    name: str
    location: str
    cabinet_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: CabinetState = CabinetState.DRAFT
