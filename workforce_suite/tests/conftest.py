"""Reject accidental cross-bench connections during an isolated integration run."""
import os
from pathlib import Path


def pytest_configure(config):
    sites = os.environ.get("FRAPPE_TEST_SITES_PATH")
    site = os.environ.get("FRAPPE_TEST_SITE")
    if not (sites and site):
        return  # Source-only QA has no Frappe/database dependency.
    import frappe

    original_init = frappe.init
    allowed = Path(sites).resolve()
    allowed_site = site
    os.chdir(allowed)

    def isolated_init(site=None, sites_path=".", *args, **kwargs):
        if site and (site != allowed_site or Path(sites_path).resolve() != allowed):
            raise RuntimeError("Integration test attempted to connect outside its explicit isolated site")
        result = original_init(site=site, sites_path=sites_path, *args, **kwargs)
        if site and not frappe.conf.get("workforce_rehearsal"):
            raise RuntimeError("Integration site must be explicitly marked workforce_rehearsal before connecting")
        return result

    frappe.init = isolated_init
