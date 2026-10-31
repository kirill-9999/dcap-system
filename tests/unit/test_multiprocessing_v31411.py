"""53.4m (v3.14.11): multiprocessing — ProcessPoolExecutor, picklable Finding."""

import os
import pickle
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DCAP_SCANNER_DIR = os.path.join(_ROOT, "scanner")
for _p in (_ROOT, _DCAP_SCANNER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.finding import Finding  # noqa: E402


def test_finding_picklable():
    """Finding с metadata.locations[] — picklable."""
    f = Finding(
        line_number=1,
        line_text="x",
        match_text="test@example.com",
        start_pos=0,
        end_pos=16,
        finding_type="pii",
        category="email",
        metadata={
            "locations": [
                {
                    "line": 1,
                    "start_pos": 0,
                    "end_pos": 16,
                    "context_before": "",
                    "context_after": "",
                }
            ]
        },
    )
    data = pickle.dumps(f)
    f2 = pickle.loads(data)
    assert f2.category == "email"
    assert len(f2.metadata["locations"]) == 1


def test_performance_config():
    """PerformanceConfig — executor, max_workers, chunk_size."""
    from scanner.src.config_loader import PerformanceConfig

    cfg = PerformanceConfig()
    assert cfg.executor in ("process", "thread")
    assert cfg.max_workers >= 1
    assert cfg.chunk_size >= 1


def test_executor_factory_process():
    """_get_executor('process') → ProcessPoolExecutor."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from scanner.connectors._text_scanner import _get_executor

    ex = _get_executor("process", 2)
    assert isinstance(ex, ProcessPoolExecutor)
    ex.shutdown(wait=True)
    ex = _get_executor("thread", 2)
    assert isinstance(ex, ThreadPoolExecutor)
    ex.shutdown(wait=True)


def test_classifier_spec_picklable():
    """Spec классификатора (имя + конфиг) — picklable, без экземпляра."""
    from scanner.classifiers.factory import classifier_spec

    class _Fake:
        classifier_name = "credentials_classifier"
        config = {"entropy_threshold": 4.5}

    spec = classifier_spec(_Fake())
    assert spec is not None
    assert spec["name"] == "credentials_classifier"
    assert spec["config"]["entropy_threshold"] == 4.5
    assert pickle.loads(pickle.dumps(spec))["name"] == "credentials_classifier"


def test_classifier_spec_unpicklable_config():
    """Несериализуемый config → None (коннектор уйдёт в thread-режим)."""
    from scanner.classifiers.factory import classifier_spec, classifier_specs

    class _Fake:
        classifier_name = "credentials_classifier"
        config = {"callback": lambda x: x}

    assert classifier_spec(_Fake()) is None
    assert classifier_specs([_Fake()]) is None


def test_worker_specs_limits_pii_memory():
    """В воркере: пул Presidio = 1, OCRWorker PII не стартует."""
    from scanner.classifiers.factory import worker_specs

    specs = [{"name": "pii_classifier", "config": {"analyzer_pool_size": 4, "ocr_enabled": True}}]
    out = worker_specs(specs)
    assert out[0]["config"]["analyzer_pool_size"] == 1
    assert out[0]["config"]["start_ocr_worker"] is False


class _DummyClassifier:
    classifier_name = "_dummy"

    def __init__(self):
        self.config = {}

    def configure(self, cfg):
        self.config = dict(cfg)


def test_get_classifier_per_process_cache(monkeypatch):
    """get_classifier кеширует экземпляр на процесс (повторный конфиг не применяется)."""
    from scanner.classifiers import factory

    monkeypatch.setitem(factory._REGISTRY, "_dummy", (__name__, "_DummyClassifier"))
    a = factory.get_classifier("_dummy", {"entropy_threshold": 4.0})
    first_cfg = dict(a.config)
    b = factory.get_classifier("_dummy", {"entropy_threshold": 9.9})
    assert a is b
    assert b.config == first_cfg
    assert factory.build_classifiers([{"name": "_dummy", "config": {}}]) == [a]


def test_get_classifier_unknown_name():
    """Неизвестное имя — ValueError."""
    import pytest as _pytest

    from scanner.classifiers.factory import get_classifier

    with _pytest.raises(ValueError):
        get_classifier("no_such_classifier")


def test_performance_config_top_level():
    """performance читается из верхнеуровневой секции JSON."""
    from scanner.src.config_loader import AppConfig

    cfg = AppConfig.from_dict(
        {"performance": {"executor": "thread", "max_workers": 2, "chunk_size": 7}}
    )
    assert cfg.performance.executor == "thread"
    assert cfg.performance.max_workers == 2
    assert cfg.performance.chunk_size == 7

def test_scan_path_broken_pool_keeps_findings(monkeypatch, tmp_path):
    """Падение воркера (BrokenProcessPool) не валит скан целиком."""
    import concurrent.futures as cf
    from concurrent.futures import Future
    from concurrent.futures.process import BrokenProcessPool

    from scanner.classifiers import factory
    from scanner.connectors import filesystem as fs_mod

    monkeypatch.setitem(factory._REGISTRY, "_dummy", (__name__, "_DummyClassifier"))

    class _Pool:
        def __init__(self, *a, **kw):
            self.n = 0

        def submit(self, fn, fp):
            self.n += 1
            if self.n >= 2:
                raise BrokenProcessPool("boom")
            fut = Future()
            fut.set_result([])
            return fut

        def shutdown(self, wait=True):
            pass

    monkeypatch.setattr(cf, "ProcessPoolExecutor", _Pool)

    (tmp_path / "a.txt").write_text("pass", encoding="utf-8")
    (tmp_path / "b.txt").write_text("pass", encoding="utf-8")

    conn = fs_mod.FilesystemConnector(
        {
            "max_parallel_files": 2,
            "performance": {"executor": "process", "max_workers": 2, "chunk_size": 10},
        }
    )
    out = conn.scan_path(str(tmp_path), [_DummyClassifier()])
    assert out == []
