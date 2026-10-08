"""Installed native UI behavior, without app DOM interception."""
import json
import subprocess
from pathlib import Path

FRAPPE = Path('/home/sanchita/frappe-bench-v16/apps/frappe/frappe')
NODE = '/home/sanchita/.nvm/versions/node/v24.15.0/bin/node'


def test_installed_native_relative_app_route_and_sidebar_route():
    source = (FRAPPE / 'desk/page/desktop/desktop.js').read_text()
    start = source.index('function get_route(desktop_icon) {')
    end = source.index('\nfunction ', start + 1)
    function = source[start:end]
    js = '''const window={location:{origin:"http://synthetic.local"}};
    const frappe={boot:{workspace_sidebar_item:{'workforce hr':{items:[{type:'Link',link_type:'Workspace',link_to:'workforce-suite'}]}}},workspaces:{'workforce-suite':{title:'Workforce Suite',public:1}},router:{slug:x=>x.toLowerCase().replaceAll(' ','-')},utils:{generate_route:()=>"/desk/workforce-suite?sidebar=Workforce%20HR"}};
    FUNCTION
    console.log(JSON.stringify([get_route({link_type:'External',link:'/app/workforce-suite'}),get_route({label:'Workforce Suite',link_type:'Workspace Sidebar'})]));'''.replace('FUNCTION', function)
    result = subprocess.check_output([NODE, '-e', js], text=True)
    assert json.loads(result) == ['http://synthetic.local/app/workforce-suite', '/desk/workforce-suite?sidebar=Workforce%20HR']
    assert 'this.icon_route.startsWith("http")' in source
    icon = json.loads((Path(__file__).resolve().parents[1] / 'desktop_icon/workforce_suite.json').read_text())
    assert icon['standard'] == 1 and icon['icon_type'] == 'App'
    assert icon['link_type'] == 'Workspace Sidebar' and icon['label'] == 'Workforce Suite'
    assert not icon.get('link_to') and not icon.get('sidebar')  # No fresh-install Link dependency.
    sync = (FRAPPE / 'model/sync.py').read_text()
    assert 'app_level_folders = ["desktop_icon",' in sync
    meta = json.loads((FRAPPE / 'desk/doctype/desktop_icon/desktop_icon.json').read_text())
    fields = {f['fieldname']: f for f in meta['fields']}
    assert set(icon) - set(fields) - {'doctype', 'name', 'modified'} == set()
    for name in ('link_type', 'icon_type'):
        assert icon[name] in fields[name]['options'].split('\n')


def test_installed_theme_switcher_retains_native_modes_keyboard_and_persistence():
    source = (FRAPPE / 'public/js/frappe/ui/theme_switcher.js').read_text()
    assert 'name: "automatic"' in source
    assert 'frappe.core.doctype.user.user.switch_theme' in source
    assert 'e.keyCode === 13' in source
    assert 'key === "right"' in source and 'key === "left"' in source
