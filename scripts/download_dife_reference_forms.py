#!/usr/bin/env python3
"""Audit and retrieve public DIFE Khulna PDF references (not live app assets).

Never used by install hooks or payroll. Keeps a receipt with SHA256 and page
counts, and fails on unavailable/non-PDF sources. No customer data is involved.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOST = "objectstorage.ap-dcc-gazipur-1.oraclecloud15.com"
MAX_BYTES = 20 * 1024 * 1024
CATALOG = Path(__file__).resolve().parents[1] / "docs/bangladesh/dife_form_sources.json"


def validate_catalog():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = catalog["entries"]
    if len(entries) != 29 or [r["index"] for r in entries] != list(range(1, 30)):
        raise ValueError("Source catalog must have the 29 ordered checklist entries")
    if len(set(r["id"] for r in entries)) != len(entries):
        raise ValueError("Duplicate source catalog identifiers")
    for row in entries:
        u = urlsplit(row["source_pdf_url"])
        if u.scheme != "https" or u.hostname != HOST or not u.path.endswith(".pdf"):
            raise ValueError("Non-official reference URL for " + row["id"])
        if row["print_template_status"] != "not_implemented":
            raise ValueError("This inventory cannot mark a print template implemented")
    return catalog


def fetch(row, out, timeout, retries):
    dest = out / (row["id"] + ".pdf")
    last_error = ""
    for attempt in range(retries + 1):
        try:
            req = Request(row["source_pdf_url"], headers={
                "User-Agent": "WorkforceSuite-DIFE-PublicReference-Audit/1.0",
                "Accept": "application/pdf",
            })
            with urlopen(req, timeout=timeout) as response:
                redirected = urlsplit(response.geturl())
                if redirected.scheme != "https" or redirected.hostname != HOST:
                    raise ValueError("Unexpected redirect away from official PDF host")
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
                raise ValueError("Too large or not an actual PDF")
            from pypdf import PdfReader
            pages = len(PdfReader(BytesIO(data), strict=False).pages)
            if pages < 1:
                raise ValueError("No PDF pages")
            temp = dest.with_suffix(".part")
            temp.write_bytes(data)
            temp.replace(dest)
            return dict(index=row["index"], id=row["id"], status="downloaded",
                        bytes=len(data), pages=pages,
                        sha256=hashlib.sha256(data).hexdigest(),
                        file=dest.name, url=row["source_pdf_url"])
        except Exception as e:
            last_error = type(e).__name__ + ": " + str(e)[:180]
            if attempt < retries:
                time.sleep(2 + attempt * 2)
    return dict(index=row["index"], id=row["id"], status="unavailable",
                error=last_error, url=row["source_pdf_url"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="offline catalog validation only")
    p.add_argument("--download", action="store_true", help="retrieve verified PDFs")
    p.add_argument("--output", default="dife_references")
    p.add_argument("--timeout", type=int, default=22)
    p.add_argument("--retries", type=int, default=1)
    p.add_argument("--workers", type=int, default=2)
    args = p.parse_args()
    cat = validate_catalog()
    rows = cat["entries"]
    print("Verified manifest entries:", len(rows))
    print("Prior web PDF previews:", sum(r["web_preview"]["opened"] for r in rows))
    if args.check:
        return 0
    if not args.download:
        p.error("Specify --check or --download")
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=min(3, max(1, args.workers))) as pool:
        futs = [pool.submit(fetch, row, target, args.timeout, args.retries) for row in rows]
        for future in as_completed(futs):
            result = future.result()
            results.append(result)
            print(str(result["index"]).zfill(2), result["id"], result["status"], flush=True)
    results.sort(key=lambda r: r["index"])
    completed = sum(x["status"] == "downloaded" for x in results)
    receipt = {
        "source": cat["source"],
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "requested": len(results), "downloaded": completed,
        "unavailable": len(results) - completed,
        "note": "These are reference PDFs, not verified legally compliant dynamic print formats.",
        "results": results,
    }
    (target / "download_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print("Downloaded:", completed, "Unavailable:", len(results) - completed)
    return 0 if completed == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
