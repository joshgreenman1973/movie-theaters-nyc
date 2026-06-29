"""
Build data/theaters.json for the front-end from the raw Cinema Treasures pull,
merging in the enriched opened/closed years when available.

Re-runnable: if data/enrich/years_slice_*.json exist, their (high-quality,
description-derived) years override the raw regex guesses. Otherwise the raw
guesses are used and every record is flagged provisional.
"""
import csv, json, glob, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

YEAR_MIN, YEAR_MAX = 1880, 2026
OPEN_STATUSES = {"Open", "Renovating", "Restoring"}


def to_year(v):
    """Parse a 4-digit year. Tolerates decade strings ('1950s', 'early 1960s')
    by taking the decade's first year."""
    if v is None:
        return None
    m = re.search(r"(18|19|20)\d{2}", str(v))
    if not m:
        return None
    y = int(m.group(0))
    return y if YEAR_MIN <= y <= YEAR_MAX else None


def load_enriched():
    """Return {id: {opened, closed, demolished, confidence}} from enrichment files."""
    out = {}
    files = glob.glob(os.path.join(DATA, "enrich", "years_slice_*.json"))
    for f in files:
        try:
            arr = json.load(open(f))
        except Exception:
            continue
        for rec in arr:
            tid = str(rec.get("id", "")).strip()
            if not tid:
                continue
            out[tid] = rec
    return out


def main():
    raw = list(csv.DictReader(open(os.path.join(DATA, "cinema_treasures_raw.csv"))))
    enriched = load_enriched()
    have_enrich = len(enriched) > 0

    theaters = []
    stats = {"total": 0, "with_open": 0, "with_close": 0, "undated": 0,
             "timeline": 0, "enriched_used": 0, "still_open": 0}

    for r in raw:
        tid = r["cinema_treasures_id"].strip()
        lat = r["latitude"].strip()
        lng = r["longitude"].strip()
        if not lat or not lng:
            continue  # cannot place on the map
        status = r["status"].strip()
        seats = to_int(r["seats"])
        screens = to_int(r["screens"])

        opened = closed = None
        demolished = None
        confidence = "low"
        provisional = True

        en = enriched.get(tid)
        if en:
            opened = to_year(en.get("opened")) if en.get("opened") not in (None, "unknown", "") else None
            cval = en.get("closed")
            if cval in ("still_open",):
                closed = None
            else:
                closed = to_year(cval)
            demolished = to_year(en.get("demolished")) if en.get("demolished") not in (None, "na", "unknown", "") else None
            confidence = (en.get("confidence") or "low").strip().lower()
            provisional = False
            stats["enriched_used"] += 1
        else:
            opened = to_year(r["year_opened_guess"])
            closed = to_year(r["year_closed_guess"])

        # Coherence: open theaters have no death year.
        is_open = status in OPEN_STATUSES
        if is_open:
            closed = None
        # The light goes out when the theater CLOSES (stops showing movies), not when
        # the building is later demolished. Fall back to the demolition year only when
        # the closing year is unknown.
        gone = None
        if not is_open:
            gone = closed if closed else demolished
        # drop impossible orderings
        if opened and gone and gone < opened:
            gone = None
            confidence = "low"
        # A theater belongs on the animated timeline only if we know when it appeared
        # and (if it's gone) when it went dark. Otherwise it would sit falsely lit.
        timeline = (opened is not None) and (is_open or gone is not None)

        rec = {
            "id": tid,
            "name": r["name"].strip(),
            "borough": r["borough"].strip(),
            "lat": round(float(lat), 6),
            "lng": round(float(lng), 6),
            "seats": seats,
            "screens": screens,
            "status": status,
            "opened": opened,
            "gone": gone,            # year the lights went out (closed), or None if still open
            "open_now": is_open,
            "timeline": timeline,
            "confidence": confidence,
            "provisional": provisional,
            "url": r["cinema_treasures_url"].strip(),
            "address": r["full_address"].strip(),
        }
        theaters.append(rec)
        stats["total"] += 1
        if opened:
            stats["with_open"] += 1
        if gone:
            stats["with_close"] += 1
        if timeline:
            stats["timeline"] += 1
        else:
            stats["undated"] += 1
        if rec["open_now"]:
            stats["still_open"] += 1

    out = {
        "generated_provisional": not have_enrich,
        "stats": stats,
        "theaters": theaters,
    }
    with open(os.path.join(DATA, "theaters.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print("enriched files found:", have_enrich, "| records merged from enrichment:", stats["enriched_used"])
    print(json.dumps(stats, indent=2))


def to_int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None


if __name__ == "__main__":
    main()
