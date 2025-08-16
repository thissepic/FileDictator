# schemas.py
from typing import List, Type, Optional
from pydantic import BaseModel, field_validator, ConfigDict


def build_docsort_model(allowed_paths: List[str]) -> Type[BaseModel]:
    """
    Erzeugt zur Laufzeit ein Pydantic-Modell mit:
      - target_path nur aus allowed_paths
      - confidence in [0, 1]
      - reason: str
      - alternatives: List[str] (optional)
    """
    if not allowed_paths:
        raise ValueError("allowed_paths darf nicht leer sein")

    class DocSortResult(BaseModel):
        model_config = ConfigDict(extra="forbid")

        target_path: str
        confidence: float
        reason: str
        tags: List[str]
        caption: Optional[str] = None
        alternatives: List[str] = []

        @field_validator("target_path")
        @classmethod
        def _path_in_whitelist(cls, v: str) -> str:
            if v not in allowed_paths:
                raise ValueError(f"'{v}' ist kein zulässiger Zielpfad")
            return v

        @field_validator("confidence")
        @classmethod
        def _conf_range(cls, v: float) -> float:
            if not (0.0 <= v <= 1.0):
                raise ValueError("confidence muss in [0,1] liegen")
            return v

        @field_validator("tags")
        @classmethod
        def _tags_nonempty(cls, v: List[str]) -> List[str]:
            if not v:
                raise ValueError("mindestens 1 Tag erforderlich")
            return [t.strip() for t in v if t and t.strip()]

    return DocSortResult
