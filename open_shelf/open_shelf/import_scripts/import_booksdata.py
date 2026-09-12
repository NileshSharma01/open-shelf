"""
Open Shelf — Booksdata XLSX importer.

Reads the 'Booksdata' sheet from the real workbook, normalizes and
aggregates it, resolves/creates Author/Publisher/Category/Distributor
link records, then hands the result to the EXISTING, already-tested
`import_bulk_data("Book", csv_data, dry_run)` function in
open_shelf.api.api — so all of that function's proven ISBN-matching,
update-not-duplicate, and copy-count safety logic is reused as-is.

USAGE (run via bench, from anywhere inside the bench):

    bench --site openshelf.localhost execute \
        open_shelf.import_scripts.import_booksdata.run \
        --kwargs "{'xlsx_path': '/home/asus/frappe-bench/import_data/Book_Database.xlsx', 'dry_run': 1}"

ALWAYS run with dry_run=1 first. Read the printed report carefully.
Only re-run with dry_run=0 once the dry-run report looks correct.

Notes on decisions baked into this script (confirmed with the user):
  - Binding -> Book.edition. Format/Genre Type/Comment/Goodreads Link
    are intentionally NOT imported (no matching Book field).
  - total_copies = summed 'Quantity' column across duplicate-ISBN rows
    (lifetime total, includes historically sold copies).
    available_copies = summed 'Available Qty' across duplicate-ISBN rows.
    Per the user's own confirmed business rule, duplicate ISBNs in this
    workbook represent genuinely separate physical copies, so rows are
    SUMMED here (not deduped by max) before ever reaching
    import_bulk_data's own generic dedup logic -- each ISBN is only
    ever presented to it once, so that function's tested logic is
    left completely untouched.
  - ISBN values that are not real ISBN-13 digit strings (e.g. "(Code
    1080)", "-", "9789326330195A") are treated the same as a blank
    ISBN: fallback-matched by normalized title/author, else created
    as a new Book with no ISBN.
"""

import csv
import io
import re

import frappe
import openpyxl

SHEET_NAME = "Booksdata"

VALID_ISBN_RE = re.compile(r"^\d{10}(\d{3})?$")

LINK_FIELDS = {
    "author": ("Author", "author_name"),
    "publisher": ("Publisher", "publisher_name"),
    "category": ("Category", "category_name"),
    "distributor": ("Distributor", "distributor_name"),
}

CSV_FIELDNAMES = [
    "name",
    "isbn",
    "book_title",
    "author",
    "publisher",
    "category",
    "edition",
    "language",
    "publication_year",
    "selling_price",
    "total_copies",
    "available_copies",
    "distributor",
]


def _clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none", "n/a", "null"):
        return ""
    return s


def _norm_isbn(raw):
    if raw is None:
        return "", None
    if isinstance(raw, int):
        s = str(raw)
    elif isinstance(raw, float):
        s = str(int(raw))
    else:
        s = str(raw).strip()
    compact = s.replace(" ", "").replace("-", "")
    if VALID_ISBN_RE.match(compact):
        return compact, None
    return "", (s if s else None)


def _norm_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _num(v):
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _resolve_link(field, raw_value, cache, dry_run, to_create, created_counts):
    raw_value = _clean(raw_value)
    if not raw_value:
        return ""

    doctype, content_field = LINK_FIELDS[field]
    cache_key = (field, _norm_key(raw_value))
    if cache_key in cache:
        return cache[cache_key] or ""

    existing = frappe.db.get_value(doctype, {content_field: raw_value}, "name")
    if not existing:
        existing = frappe.db.get_value(
            doctype, {content_field: ["like", raw_value]}, "name"
        )

    if existing:
        cache[cache_key] = existing
        return existing

    if dry_run:
        to_create.setdefault(field, set()).add(raw_value)
        cache[cache_key] = None
        return ""

    doc = frappe.get_doc({"doctype": doctype, content_field: raw_value})
    doc.insert(ignore_permissions=True)
    created_counts[field] = created_counts.get(field, 0) + 1
    cache[cache_key] = doc.name
    return doc.name


def _find_fallback_match(title, author, publisher):
    if not title:
        return None

    candidates = frappe.get_all(
        "Book",
        filters={"book_title": ["like", title]},
        fields=["name", "book_title", "author", "publisher"],
        limit_page_length=20,
    )

    title_key = _norm_key(title)
    author_key = _norm_key(author)

    best = None
    for c in candidates:
        if _norm_key(c.get("book_title")) != title_key:
            continue
        if author_key and c.get("author"):
            if _norm_key(c.get("author")) == author_key:
                return c["name"]
            best = best or c["name"]
        else:
            best = best or c["name"]
    return best


def _read_rows(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        frappe.throw(f"Sheet '{SHEET_NAME}' not found. Sheets: {wb.sheetnames}")
    ws = wb[SHEET_NAME]

    header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    idx = {name: i for i, name in enumerate(header) if name}

    required = ["ISBN-13", "Title", "Author's name", "Publisher"]
    missing = [c for c in required if c not in idx]
    if missing:
        frappe.throw(f"Expected columns missing from '{SHEET_NAME}': {missing}")

    def get(row, col):
        i = idx.get(col)
        return row[i] if i is not None and i < len(row) else None

    row_num = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        row_num += 1
        title = _clean(get(row, "Title"))
        if not title:
            continue
        yield row_num, {
            "book_title": title,
            "isbn_raw": get(row, "ISBN-13"),
            "author": _clean(get(row, "Author's name")),
            "publisher": _clean(get(row, "Publisher")),
            "category": _clean(get(row, "OSRF Category")),
            "edition": _clean(get(row, "Binding")),
            "language": _clean(get(row, "Language")),
            "publication_year": _clean(get(row, "Release Year")),
            "selling_price": _clean(get(row, "Price")),
            "distributor": _clean(get(row, "Distributors")),
            "available_qty": _num(get(row, "Available Qty")),
            "rented_qty": _num(get(row, "Rented Qty")),
            "sold_qty": _num(get(row, "Sold out Qty")),
            "quantity": _num(get(row, "Quantity")),
        }


def _aggregate(xlsx_path):
    isbn_groups = {}
    no_isbn_records = []
    junk_isbn_examples = []
    total_rows = 0

    for row_num, rec in _read_rows(xlsx_path):
        total_rows += 1
        isbn, junk = _norm_isbn(rec["isbn_raw"])

        if not isbn:
            if junk:
                junk_isbn_examples.append((row_num, rec["book_title"], junk))
            rec["source_rows"] = [row_num]
            no_isbn_records.append(rec)
            continue

        if isbn not in isbn_groups:
            isbn_groups[isbn] = {
                "isbn": isbn,
                "book_title": rec["book_title"],
                "author": rec["author"],
                "publisher": rec["publisher"],
                "category": rec["category"],
                "edition": rec["edition"],
                "language": rec["language"],
                "publication_year": rec["publication_year"],
                "selling_price": rec["selling_price"],
                "distributor": rec["distributor"],
                "available_qty": 0.0,
                "rented_qty": 0.0,
                "sold_qty": 0.0,
                "quantity": 0.0,
                "source_rows": [],
            }

        g = isbn_groups[isbn]
        g["source_rows"].append(row_num)
        g["available_qty"] += rec["available_qty"]
        g["rented_qty"] += rec["rented_qty"]
        g["sold_qty"] += rec["sold_qty"]
        g["quantity"] += rec["quantity"]

        for f in (
            "author",
            "publisher",
            "category",
            "edition",
            "language",
            "publication_year",
            "selling_price",
            "distributor",
            "book_title",
        ):
            if not g.get(f) and rec.get(f):
                g[f] = rec[f]

    stats = {
        "total_rows": total_rows,
        "isbn_groups": len(isbn_groups),
        "duplicate_isbn_rows_consolidated": sum(
            len(g["source_rows"]) - 1 for g in isbn_groups.values()
        ),
        "no_isbn_rows": len(no_isbn_records),
        "junk_isbn_examples": junk_isbn_examples[:10],
    }
    return isbn_groups, no_isbn_records, stats


def run(xlsx_path, dry_run=1):
    dry_run = bool(int(dry_run))
    frappe.set_user("Administrator")

    from open_shelf.api.api import import_bulk_data

    isbn_groups, no_isbn_records, stats = _aggregate(xlsx_path)

    link_cache = {}
    to_create = {}
    created_counts = {}
    fallback_matched = 0
    fallback_created = 0

    csv_rows = []

    for isbn, g in isbn_groups.items():
        csv_rows.append(
            {
                "name": "",
                "isbn": isbn,
                "book_title": g["book_title"],
                "author": _resolve_link(
                    "author", g["author"], link_cache, dry_run, to_create, created_counts
                ),
                "publisher": _resolve_link(
                    "publisher", g["publisher"], link_cache, dry_run, to_create, created_counts
                ),
                "category": _resolve_link(
                    "category", g["category"], link_cache, dry_run, to_create, created_counts
                ),
                "edition": g["edition"],
                "language": g["language"],
                "publication_year": (
                    (
            int(float(str(g["publication_year"]).strip()))
            if str(g["publication_year"]).strip().replace(".", "", 1).isdigit()
            else ""
        )
                ),
                "selling_price": g["selling_price"],
                "total_copies": int(g["quantity"]),
                "available_copies": int(g["available_qty"]),
                "distributor": _resolve_link(
                    "distributor",
                    g["distributor"],
                    link_cache,
                    dry_run,
                    to_create,
                    created_counts,
                ),
            }
        )

    for rec in no_isbn_records:
        match_name = _find_fallback_match(
            rec["book_title"], rec["author"], rec["publisher"]
        )
        if match_name:
            fallback_matched += 1
        else:
            fallback_created += 1

        csv_rows.append(
            {
                "name": match_name or "",
                "isbn": "",
                "book_title": rec["book_title"],
                "author": _resolve_link(
                    "author", rec["author"], link_cache, dry_run, to_create, created_counts
                ),
                "publisher": _resolve_link(
                    "publisher", rec["publisher"], link_cache, dry_run, to_create, created_counts
                ),
                "category": _resolve_link(
                    "category", rec["category"], link_cache, dry_run, to_create, created_counts
                ),
                "edition": rec["edition"],
                "language": rec["language"],
                "publication_year": (
                    int(rec["publication_year"]) if str(rec["publication_year"]).strip() else ""
                ),
                "selling_price": rec["selling_price"],
                "total_copies": int(rec["quantity"]),
                "available_copies": int(rec["available_qty"]),
                "distributor": _resolve_link(
                    "distributor",
                    rec["distributor"],
                    link_cache,
                    dry_run,
                    to_create,
                    created_counts,
                ),
            }
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)
    csv_data = output.getvalue()

    if dry_run and to_create:
        print("=" * 70)
        print("DRY RUN — master records that WOULD BE CREATED (none created yet):")
        for field, values in to_create.items():
            print(f"  {field} ({len(values)} new):")
            for v in sorted(values)[:15]:
                print(f"    - {v}")
            if len(values) > 15:
                print(f"    ... and {len(values) - 15} more")
        print("=" * 70)
        print(
            "NOTE: rows needing these will show blank for that link field in this "
            "dry run preview. Run with dry_run=0 to create them and link properly."
        )

    result = import_bulk_data("Book", csv_data, dry_run=1 if dry_run else 0)

    print("=" * 70)
    print("SOURCE STATS")
    print(f"  Excel rows read:                     {stats['total_rows']}")
    print(f"  Unique ISBN groups:                  {stats['isbn_groups']}")
    print(f"  Duplicate ISBN rows consolidated:     {stats['duplicate_isbn_rows_consolidated']}")
    print(f"  No usable ISBN (blank or junk):       {stats['no_isbn_rows']}")
    print(f"    -> fallback-matched to existing Book: {fallback_matched}")
    print(f"    -> will be created as new Book:       {fallback_created}")
    if stats["junk_isbn_examples"]:
        print("  Junk ISBN examples (row, title, raw value):")
        for r in stats["junk_isbn_examples"]:
            print(f"    {r}")
    if not dry_run and created_counts:
        print("  Master records created:")
        for field, count in created_counts.items():
            print(f"    {field}: {count}")
    print("=" * 70)
    print(f"import_bulk_data result (dry_run={dry_run}):")
    print(result)
    print("=" * 70)

    return {
        "stats": stats,
        "fallback_matched": fallback_matched,
        "fallback_created": fallback_created,
        "to_create": {k: sorted(v) for k, v in to_create.items()},
        "created_counts": created_counts,
        "import_result": result,
    }
