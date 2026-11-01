from pathlib import Path

import yaml
from pydantic import BaseModel

from sarthi.core.models import DocType


class SourceSpec(BaseModel):
    id: str
    url: str
    doc_type: DocType
    publisher: str
    title: str


def load_registry(path: Path) -> list[SourceSpec]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [SourceSpec(**entry) for entry in data["sources"]]
