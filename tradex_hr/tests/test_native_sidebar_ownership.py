"""Controlled installer projections: never connect to or mutate shared staging."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import frappe
from tradex_hr import install

ROOT = Path(__file__).resolve().parents[1]
FRAPPE = Path("/home/sanchita/frappe-bench-v16/apps/frappe/frappe")

class ProjectedDoc(frappe._dict):
    def set(self,key,value): self[key]=copy.deepcopy(value)
    def append(self,key,value): self.setdefault(key,[]).append(copy.deepcopy(value))
    def save(self,**kwargs): return self
    def insert(self,**kwargs): return self
    def is_new(self): return False

@pytest.fixture
def projection(monkeypatch):
    records={
        ("Workspace Sidebar","Tradexcel HR"):ProjectedDoc(title="Tradexcel HR",items=[{"label":"Public admin customization"}]),
        ("Workspace Sidebar","Tradexcel HR-Administrator"):ProjectedDoc(for_user="Administrator",items=[{"label":"Personal custom route"}]),
        ("Workspace Sidebar","Unrelated"):ProjectedDoc(items=[{"label":"Other"}]),
        ("Workspace","tradexcel-hr"):ProjectedDoc(name="tradexcel-hr"),
    }
    touched=[]
    def exists(dt,name): return dt=="DocType" or (dt,name) in records
    def get_doc(dt,name):
        touched.append((dt,name));return records[(dt,name)]
    fake=SimpleNamespace(db=SimpleNamespace(exists=exists),get_doc=get_doc,
        flags=SimpleNamespace(in_migrate=False))
    monkeypatch.setattr(install,"frappe",fake)
    monkeypatch.setattr(install,"ensure_action_board_block",lambda:None)
    monkeypatch.setattr(install,"ensure_operator_guidance",lambda:None)
    return records,touched

def test_complete_installer_projection_repeated_sync_and_personal_preservation(projection):
    records,touched=projection
    preserved=copy.deepcopy({k:v for k,v in records.items() if k[0]=="Workspace Sidebar" and k[1]!="Tradexcel HR"})
    # Exercise actual ensure_workspace population, including available bulk tools.
    install.ensure_workspace()
    public=records[("Workspace Sidebar","Tradexcel HR")]
    expected=install.workspace_sidebar_items(list(install.WORKSPACE_SHORTCUTS)+list(install.BULK_WORKSPACE_SHORTCUTS))
    assert public["items"]==expected
    for label,target,kind in install.BULK_WORKSPACE_SHORTCUTS:
        assert any(r.get("label")==label and r.get("link_to")==target for r in public["items"])
    first=copy.deepcopy(public)
    install.ensure_workspace()
    assert public==first
    assert {k:records[k] for k in preserved}==preserved
    assert set(touched)=={("Workspace Sidebar","Tradexcel HR"),("Workspace","tradexcel-hr")}
    assert public.standard==0 and public.for_user is None
    # Public administrator edits are rewritten, NOT preserved by this installer.
    public["items"].append({"label":"Another public custom route"})
    install.ensure_workspace()
    assert public["items"]==expected


def test_sidebar_sync_source_and_native_selectors():
    assert 'app_level_folders = ["desktop_icon", "workspace_sidebar", "sidebar_item_group"]' in (FRAPPE/"model/sync.py").read_text()
    scss=(FRAPPE/"public/scss/desk/sidebar.scss").read_text()
    js=(FRAPPE/"public/js/frappe/ui/sidebar/sidebar.js").read_text()
    assert ".body-sidebar-container" in scss and ".body-sidebar-container.expanded" in scss
    assert "data-sidebar-expanded" not in js
    assert "width: 50px" in scss and "overflow-y: auto" in scss


def test_native_desktop_icon_contract():
    icon=json.loads((ROOT/"desktop_icon/tradexcel_hr.json").read_text())
    assert icon["link_type"]=="Workspace Sidebar" and icon["standard"]==1
    assert icon["label"]=="Tradexcel HR"
    source=(FRAPPE/"desk/page/desktop/desktop.js").read_text()
    assert "workspace_sidebar_item" in source
