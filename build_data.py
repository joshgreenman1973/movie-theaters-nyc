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
# Dedicated movie theaters (nickelodeons) did not exist in NYC before ~1905; the first
# projected film here was 1896 (Koster & Bial's Music Hall), shown within vaudeville
# programs, not in movie theaters. Cinema Treasures records a venue's BUILDING opening
# year, which for older houses long predates any film use. So for the movie-theater
# timeline we floor the effective opening at the movie era and keep the building year
# separately. See METHODOLOGY.md.
MOVIE_ERA = 1905

# Named repertory/arthouse houses that the crowdsourced source left undated or recorded
# only under their later non-cinema identity. Years here are recovered from secondary
# sources (Wikipedia, Village Preservation) and cited in METHODOLOGY.md. Keyed by
# Cinema Treasures id. open_now=False forces them off the "still open" set.
MANUAL_OVERRIDES = {
    # Bleecker Street Cinema — founded by Lionel Rogosin 1960; closed Sept 6, 1990.
    "6016": {"opened": 1960, "closed": 1990, "open_now": False, "confidence": "high"},
    # Theatre 80 St. Marks — revival film house from Aug 1971 into the mid-1990s.
    "4698": {"opened": 1971, "closed": 1994, "open_now": False, "confidence": "medium"},
    # Elgin Theater (Chelsea) — showed films 1942-1978; became the Joyce Theater (dance) 1982.
    "6353": {"opened": 1942, "closed": 1978, "open_now": False, "confidence": "high",
             "name": "Elgin Theater (now the Joyce)"},
    # Grand palaces that Cinema Treasures marks "open" because the building was restored as a
    # CONCERT/EVENT venue, not a movie theater. Dated to when they stopped showing films.
    "55":   {"closed": 1979, "open_now": False, "confidence": "high"},   # Radio City Music Hall
    "618":  {"closed": 1962, "open_now": False, "confidence": "high"},   # Brooklyn Paramount
    "1360": {"closed": 1977, "open_now": False, "confidence": "high"},   # Loew's Kings
    "44":   {"closed": 1969, "open_now": False, "confidence": "high"},   # United Palace (Loew's 175th)
    "42":   {"closed": 1974, "open_now": False, "confidence": "high"},   # Beacon Theatre
    "1865": {"closed": 1977, "open_now": False, "confidence": "high"},   # St. George Theatre
    "1864": {"closed": 1978, "open_now": False, "confidence": "high"},   # Paramount (Staten Island)
}

# A venue that Cinema Treasures lists as "open" is only an ACTIVE movie theater here if it
# actually screens films to the public today. Real current cinemas are recognized by name
# (chains + named art houses) or by an explicit keep-list of public film venues. Everything
# else CT marks open (Broadway houses, concert palaces, churches, arts centers) is treated as
# no longer a movie theater.
CURRENT_CINEMA_NAME = re.compile(
    r"\b(AMC|Regal|Cinepolis|Cin[eé]polis|Alamo|Angelika|IFC|Metrograph|Nitehawk|Nighthawk|"
    r"Film Forum|Anthology|Village East|Cinema|Cinemas|Maysles|Moving Image|Cobble Hill|"
    r"Kew Gardens|Drafthouse|Showcase|Multiplex|Movieplex|Syndicated|Stuart|Rooftop|"
    r"Paris Theater|BAM Rose|Look Cinemas|Roxy Cinema)\b", re.I)
# Public film venues whose names don't match the pattern above (kept lit).
CINEMA_KEEP_IDS = {
    "36174",  # Film at Lincoln Center
    "7846",   # Walter Reade Theater
    "36271",  # Spectacle Theater
    "4030",   # Fair Theatre
    "68759",  # Japan Society (public film series)
    "285",    # Symphony Space / Leonard Nimoy Thalia (public film programming)
}


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
             "timeline": 0, "enriched_used": 0, "still_open": 0, "predates_movie_era": 0,
             "reclassified_not_cinema": 0}

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

        # Sourced manual overrides for named houses the source mis-recorded.
        ov = MANUAL_OVERRIDES.get(tid)
        override_name = None
        if ov:
            if "opened" in ov:
                opened = ov["opened"]
            if "closed" in ov:
                closed = ov["closed"]
            if "demolished" in ov:
                demolished = ov["demolished"]
            confidence = ov.get("confidence", confidence)
            override_name = ov.get("name")
            provisional = False

        # Coherence: open theaters have no death year.
        is_open = status in OPEN_STATUSES
        if ov and "open_now" in ov:
            is_open = ov["open_now"]

        # The building may be alive without being a public movie theater. Only count it as
        # currently open if it actually screens films to the public today.
        name = override_name or r["name"].strip()
        reclassified = False
        if is_open and not (CURRENT_CINEMA_NAME.search(name) or tid in CINEMA_KEEP_IDS):
            is_open = False
            reclassified = True
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

        # Effective movie-theater opening: never earlier than the movie era. Keep the
        # building's true opening year separately for the detail card.
        building_opened = opened
        predates_movie_era = opened is not None and opened < MOVIE_ERA
        eff_opened = max(opened, MOVIE_ERA) if opened is not None else None

        # A theater is on the animated timeline only if we know when it opened (as a movie
        # house) and (if gone) when it went dark. A venue that closed before the movie era
        # never operated as a movie theater, so it is excluded.
        if eff_opened is not None and gone is not None and gone < eff_opened:
            timeline = False
        else:
            timeline = (eff_opened is not None) and (is_open or gone is not None)

        rec = {
            "id": tid,
            "name": name,
            "borough": r["borough"].strip(),
            "lat": round(float(lat), 6),
            "lng": round(float(lng), 6),
            "seats": seats,
            "screens": screens,
            "status": status,
            "opened": eff_opened,    # effective movie-theater opening (floored at movie era)
            "building_opened": building_opened,  # true building opening per Cinema Treasures
            "predates_movie_era": predates_movie_era,
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
        if predates_movie_era and timeline:
            stats["predates_movie_era"] += 1
        if reclassified:
            stats["reclassified_not_cinema"] += 1

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
