"""Contract test: the biometric resolver and its check-in writer must agree.

This exists because they did not. `_employee_map()` selects
`a.name AS assignment, a.employee, ...` while `_insert_checkin()` read
`employee["name"]` — a key the resolver never provides — so every punch raised
`KeyError: 'name'` and **no Employee Check-in could ever be created**. Neither
function was wrong on its own; only their contract was, and nothing tested it.

Two guards:

* `test_writer_only_reads_keys_the_resolver_provides` — static, no database
  needed, and fails on exactly the original bug. This is the guard that matters.
* `test_resolver_and_writer_agree_at_runtime` — exercises the real functions
  against the real site; skipped automatically when Frappe is unavailable.

Run:
    cd ~/frappe-bench
    env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests/test_biometric_worker_contract.py -q
"""

from __future__ import annotations

import ast
import pathlib
import re
import tempfile
from types import SimpleNamespace

import pytest

WORKER = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tradexcel_hr" / "biometric" / "worker.py"
)


def _function_node(name: str) -> ast.FunctionDef:
    tree = ast.parse(WORKER.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {WORKER.name}")


def _resolver_keys() -> set[str]:
    """Column names the resolver's SQL exposes on each value."""
    for node in ast.walk(_function_node("_employee_map")):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and "FROM `tabTradexcel Employee Biometric`" in node.value):
            sql = node.value
            break
    else:
        raise AssertionError("resolver SQL not found")

    select = sql[sql.upper().index("SELECT") + 6: sql.upper().index("FROM")]
    keys = set()
    for expr in select.split(","):
        expr = expr.strip()
        alias = re.search(r"\bAS\s+([A-Za-z_]\w*)\s*$", expr, re.IGNORECASE)
        keys.add(alias.group(1) if alias else expr.split(".")[-1].strip())
    return keys


def _writer_keys() -> set[str]:
    """String keys `_insert_checkin` subscripts off the employee mapping."""
    node = _function_node("_insert_checkin")
    param = "employee" if "employee" in [a.arg for a in node.args.args] else node.args.args[0].arg
    keys = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                and sub.value.id == param
                and isinstance(sub.slice, ast.Constant)
                and isinstance(sub.slice.value, str)):
            keys.add(sub.slice.value)
    return keys


def test_writer_only_reads_keys_the_resolver_provides() -> None:
    """The original bug: the writer read 'name'; the resolver provides 'employee'."""
    provided, read = _resolver_keys(), _writer_keys()
    missing = read - provided
    assert not missing, (
        f"_insert_checkin() reads {sorted(missing)} which _employee_map() does not "
        f"provide. Resolver provides {sorted(provided)}. This is the KeyError: 'name' "
        f"bug — update whichever side changed."
    )
    assert "employee" in read, (
        "the writer no longer reads an employee identifier; if the contract "
        "changed intentionally, update this test"
    )


def test_writer_does_not_reintroduce_the_name_key() -> None:
    """'name' is the assignment docname here, never the Employee id."""
    assert "name" not in _writer_keys()


# --------------------------------------------------------------------------- #
# runtime check (needs a site; skipped when unavailable)
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def site_worker():
    frappe = pytest.importorskip("frappe")
    import os
    import sys

    bench = pathlib.Path(os.environ.get("FRAPPE_TEST_BENCH", pathlib.Path.home() / "frappe-bench-v16"))
    if not (bench / "sites").is_dir():
        pytest.skip("no bench sites directory")
    try:
        frappe.init(
            site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
            sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", str(bench / "sites")),
        )
        frappe.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"cannot reach site: {type(exc).__name__}: {exc}")

    sys.path.insert(0, str(bench / "apps" / "tradex_hr"))
    from tradex_hr.tradexcel_hr.biometric.worker import ReliableBiometricWorker

    with tempfile.TemporaryDirectory() as tmp:
        worker = ReliableBiometricWorker(
            state_path=os.path.join(tmp, "state.sqlite3"), frappe_module=frappe
        )
        yield worker
        worker.close()


def test_resolver_and_writer_agree_at_runtime(site_worker) -> None:
    """The real writer must accept the real resolver value — no KeyError."""
    emap = site_worker._employee_map()
    if not emap:
        pytest.skip("no biometric assignments configured on this site")

    ambiguous = [k for k, v in emap.items() if v is None]
    assert not ambiguous, f"ambiguous (serial, PIN) keys: {ambiguous[:5]}"

    serial, pin = next(iter(emap))
    seen = []
    frappe = site_worker.frappe
    original_sql, original_get_doc = frappe.db.sql, frappe.get_doc
    frappe.db.sql = lambda *a, **k: []            # pretend no check-in exists yet
    frappe.get_doc = lambda doc: seen.append(doc) or _FakeDoc()
    try:
        result = site_worker._insert_checkin(
            emap[(serial, pin)],
            {"serial_number": serial, "event_time": "2026-01-01 09:00:00"},
            "IN",
        )
    finally:
        frappe.db.sql, frappe.get_doc = original_sql, original_get_doc

    assert result == "inserted"
    assert seen and seen[0].get("employee"), "the built check-in does not name an Employee"


class _FakeDoc:
    def insert(self, **kwargs) -> None:
        return None


def test_worker_requires_explicit_persistent_state_path():
    from tradex_hr.tradexcel_hr.biometric.worker import ReliableBiometricWorker

    with pytest.raises(ValueError, match="TRADEX_SYNC_STATE_FILE"):
        ReliableBiometricWorker(state_path=None, frappe_module=SimpleNamespace())


def test_worker_without_local_bridge_database_uses_http(tmp_path, monkeypatch):
    from tradex_hr.tradexcel_hr.biometric import worker as worker_module

    monkeypatch.setattr(worker_module, "DEFAULT_BRIDGE_DB", None)
    worker = worker_module.ReliableBiometricWorker(
        state_path=str(tmp_path / "state.sqlite3"), frappe_module=SimpleNamespace(),
    )
    try:
        monkeypatch.setattr(worker, "_fetch_http", lambda _device: [{"id": 1}])
        assert worker._fetch("SYNTHETIC-DEVICE") == [{"id": 1}]
        monkeypatch.setattr(worker_module.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
        with pytest.raises(RuntimeError, match="No devices were returned"):
            worker._discover_devices()
    finally:
        worker.close()
