
from cabinet.entity import Cabinet, CabinetState
from cabinet.lifecycle import transition

def test_valid_lifecycle():
    c = Cabinet(name="C1", location="L1", cabinet_type="CTRL")
    transition(c, CabinetState.DEFINED)
    transition(c, CabinetState.VALIDATED)
    transition(c, CabinetState.LOCKED)
    assert c.state == CabinetState.LOCKED
