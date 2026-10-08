"""TXUX-012 isolated Chromium measurements of installed native templates/assets.
Explicit run: uv run --with pytest --with playwright python -m pytest PATH -q.
No site authentication, production data or native renderer replacement.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FRAPPE = Path("/home/sanchita/frappe-bench-v16/apps/frappe/frappe")


def test_collect_native_sidebar_candidate_measurements():
    results = []
    native_css = next((FRAPPE / "public/dist/css").glob("desk.bundle*.css")).read_text()
    app_css = (ROOT / "public/css/workforce_suite.bundle.css").read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in [375, 768, 1365]:
            for height in [480, 900]:
                for theme in ["light", "dark"]:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.route(
                        "http://txux.invalid/**",
                        lambda route: route.fulfill(
                            body='<div id="host"></div>', content_type="text/html"
                        ),
                    )
                    page.goto("http://txux.invalid/")
                    page.add_style_tag(content=native_css)
                    candidate_style = page.add_style_tag(content=app_css)
                    page.add_script_tag(
                        path=str(FRAPPE / "public/js/lib/jquery/jquery.min.js")
                    )
                    page.add_script_tag(
                        content="""window.__=x=>x; window.frappe={ui:{},session:{user_fullname:'Synthetic',user_email:'synthetic@example.test'},utils:{is_rtl:()=>false,icon:()=>'<svg class="es-icon icon-sm" width="20" height="20"><rect width="16" height="16" fill="currentColor"/></svg>'}}; $.fn.tooltip=function(){return this};"""
                    )
                    page.add_script_tag(
                        content=(
                            FRAPPE / "public/js/frappe/microtemplate.js"
                        ).read_text()
                    )
                    source = (
                        FRAPPE / "public/js/frappe/ui/sidebar/sidebar.js"
                    ).read_text()
                    source = "\n".join(
                        line
                        for line in source.splitlines()
                        if not line.startswith("import ")
                    )
                    page.add_script_tag(content="class SidebarEditor{};\n" + source)
                    page.evaluate(
                        """({template,itemTemplate,theme})=>{
       document.documentElement.dataset.theme=theme;
       document.documentElement.dataset.themeMode=theme;
       $('#host').html(frappe.template.compile(template)({expanded:false,avatar:''}));
       $('.promotional-banners,.onboarding-sidebar,.dropdown-mobile').remove();
       let items='';for(let i=0;i<100;i++) items+=frappe.template.compile(itemTemplate)({item:{label:'Synthetic route '+i,type:'Link',icon:'user',standard:1},path:'#route-'+i,edit_mode:false});
       $('.sidebar-items').html(items);
       window.sidebar=Object.create(frappe.ui.Sidebar.prototype);
       sidebar.wrapper=$('.body-sidebar-container');sidebar.sidebar_expanded=false;
       sidebar.sidebar_header={toggle_width:()=>{}};
       $('.sidebar-toggle-btn').on('click',()=>{sidebar.sidebar_expanded=!sidebar.sidebar_expanded;sidebar.expand_sidebar()});
     }""",
                        dict(
                            template=(
                                FRAPPE / "public/js/frappe/ui/sidebar/sidebar.html"
                            ).read_text(),
                            itemTemplate=(
                                FRAPPE / "public/js/frappe/ui/sidebar/sidebar_item.html"
                            ).read_text(),
                            theme=theme,
                        ),
                    )
                    for expanded in [False, True]:
                        if expanded:
                            page.evaluate(
                                "sidebar.sidebar_expanded=true;sidebar.expand_sidebar()"
                            )
                        page.wait_for_timeout(350)
                        if width >= 768 or expanded:
                            page.locator(".body-sidebar").hover(
                                position={"x": 20, "y": 100}
                            )
                            page.wait_for_timeout(200)
                        result = page.evaluate("""()=>{
       const top=document.querySelector('.body-sidebar-top'),toggle=document.querySelector('.sidebar-toggle-btn'),icon=document.querySelector('.sidebar-item-icon');
       const rect=e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height});
       const a=top.querySelector('a');a.focus();
       top.scrollTop=100;const scroll=top.scrollTop;top.scrollTop=0;
       const tr=toggle.getBoundingClientRect();const point=document.elementFromPoint(tr.x+tr.width/2,tr.y+tr.height/2);
       return {hitElement:point?.className,toggleDisplay:getComputedStyle(toggle).display,sidebar:rect(document.querySelector('.body-sidebar')),top:rect(top),toggle:rect(toggle),icon:rect(icon),scrollbarWidth:top.offsetWidth-top.clientWidth,scrollable:top.scrollHeight>top.clientHeight,scrollWorked:scroll>0,toggleHit:!!point&&(point===toggle||toggle.contains(point)),focus:a===document.activeElement,overflow:document.documentElement.scrollWidth>innerWidth};
      }""")
                        result.update(
                            width=width, height=height, theme=theme, expanded=expanded
                        )
                        # Compare to native control: never convert a native/fixture limitation into
                        # a claimed app fix. Record every inaccessible hit target explicitly.
                        candidate_style.evaluate("(e)=>e.sheet.disabled=true")
                        page.wait_for_timeout(400)
                        if width >= 768 or expanded:
                            page.locator(".body-sidebar").hover(
                                position={"x": 20, "y": 100}
                            )
                            page.wait_for_timeout(200)
                        control = page.evaluate(
                            """()=>{const top=document.querySelector('.body-sidebar-top'),t=document.querySelector('.sidebar-toggle-btn'),r=t.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {overflow:document.documentElement.scrollWidth>innerWidth,toggleHit:!!hit&&(hit===t||t.contains(hit)),sidebarWidth:document.querySelector('.body-sidebar').getBoundingClientRect().width}}"""
                        )
                        candidate_style.evaluate("(e)=>e.sheet.disabled=false")
                        assert not result["overflow"] or control["overflow"], result
                        result["candidateToggleLoss"] = (
                            not result["toggleHit"] and control["toggleHit"]
                        )
                        assert not result["candidateToggleLoss"], result
                        result["nativeControl"] = control
                        if width >= 768 or expanded:
                            assert result["focus"] and result["scrollWorked"], result
                        results.append(result)
                    page.close()
        browser.close()
    Path("/tmp/txux012-measurements.json").write_text(json.dumps(results, indent=2))
    assert len(results) == 24
    # Candidate comparison success is not deployed Desk or device acceptance.
