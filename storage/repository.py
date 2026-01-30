
import json
import os
from cabinet.entity import Cabinet, CabinetState

class CabinetRepository:
    def __init__(self, base_path="data"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _path(self, cabinet_id):
        return os.path.join(self.base_path, f"{cabinet_id}.json")

    def save(self, cabinet: Cabinet):
        data = {
            "id": cabinet.id,
            "name": cabinet.name,
            "location": cabinet.location,
            "cabinet_type": cabinet.cabinet_type,
            "state": cabinet.state.value,
        }
        with open(self._path(cabinet.id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def load(self, cabinet_id) -> Cabinet:
        with open(self._path(cabinet_id), "r", encoding="utf-8") as f:
            data = json.load(f)
        return Cabinet(
            id=data["id"],
            name=data["name"],
            location=data["location"],
            cabinet_type=data["cabinet_type"],
            state=CabinetState(data["state"]),
        )
