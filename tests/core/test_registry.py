import pytest
from pydantic import ValidationError

from sarthi.core.registry import load_registry


def test_bad_doc_type_fails_at_load(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("sources:\n  - {id: a, url: 'https://e.org', doc_type: circluar, publisher: P, title: T}\n")
    with pytest.raises(ValidationError):
        load_registry(p)
