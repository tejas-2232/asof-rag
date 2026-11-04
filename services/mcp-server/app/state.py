import os
import threading
from pathlib import Path

from .models import IndexVersion, PersistentState, Promotion


class StateRepository:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "state.json"
        self._lock = threading.RLock()
        data_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> PersistentState:
        with self._lock:
            if not self.path.exists():
                return PersistentState()
            try:
                return PersistentState.model_validate_json(self.path.read_text("utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"Unable to read state from {self.path}") from exc

    def save(self, state: PersistentState) -> None:
        payload = state.model_dump_json(indent=2)
        temp = self.path.with_suffix(".tmp")
        with self._lock:
            try:
                temp.write_text(payload, encoding="utf-8")
                os.replace(temp, self.path)
            except OSError as exc:
                temp.unlink(missing_ok=True)
                raise RuntimeError(f"Unable to persist state to {self.path}") from exc

    def register_candidate(self, index: IndexVersion) -> PersistentState:
        with self._lock:
            state = self.load()
            state.indexes[index.id] = index
            state.candidate_id = index.id
            self.save(state)
            return state

    def promote(self, candidate_id: str | None = None) -> Promotion:
        with self._lock:
            state = self.load()
            selected = candidate_id or state.candidate_id
            if not selected or selected not in state.indexes:
                raise ValueError("Candidate index does not exist")
            candidate = state.indexes[selected]
            if selected == state.production_id:
                raise ValueError("Candidate is already in production")
            if candidate.stage != "candidate":
                raise ValueError("Only an isolated candidate index can be promoted")
            if candidate.evaluation.temporal_violations:
                raise ValueError("Candidate has unresolved temporal violations")

            previous = state.production_id
            if previous and previous in state.indexes:
                state.indexes[previous].stage = "retired"
            candidate.stage = "production"
            promotion = Promotion(
                candidate_id=selected,
                previous_production_id=previous,
            )
            state.production_id = selected
            if state.candidate_id == selected:
                state.candidate_id = None
            state.promotions.append(promotion)
            self.save(state)
            return promotion
