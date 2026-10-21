"""Tests for the FMH master list + catalogue. Run: python3 -m pytest service-builder/tests"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import build_master_list as b  # noqa: E402
import catalogue as c  # noqa: E402


# ---------- title cleaning ----------

@pytest.mark.parametrize("raw, title, artist", [
    ("Mighty to save (G)", "Mighty to save", ""),
    ("Same Love [Capo 2]", "Same Love", ""),
    ("Christ is Enough G", "Christ is Enough", ""),
    ("In Christ alone - Kristian Stanfill", "In Christ alone", "Kristian Stanfill"),
    ("Run to the Father: Cody Carnes", "Run to the Father", "Cody Carnes"),
    ("YOUR GRACE IS ENOUGH", "Your Grace Is Enough", ""),
    ("God_s great family (D)", "God's great family", ""),
    ("Lamb of God (C) (Case Conflict)", "Lamb of God", ""),
    ("Turn your eyes upon Jesus.doc", "Turn your eyes upon Jesus", ""),
    ("Spirit lead me G)", "Spirit lead me", ""),
])
def test_clean_title_keeps_songs(raw, title, artist):
    assert b.clean_title(raw) == (title, artist)


@pytest.mark.parametrize("raw", [
    "Verse 1", "Chorus", "[Capo 2]", "Announcements", "Worship 22 May 2016",
    "WORSHIP: 30 Jan 2021", "Psalm 113: 4-9", "Soft", "Hillsong", "E  E/G#  A2",
    "acousticguitar-1", "No Name Yet(1)", "Second time: Guitar;",
])
def test_clean_title_drops_furniture(raw):
    assert b.clean_title(raw) is None


# ---------- script dates ----------

@pytest.mark.parametrize("name, year", [
    ("2014-01-04 Worship.docx", 2014),
    ("180819 WORSHIP.docx", 2019),
    ("020521 Song and Praise and Worship.docx", 2021),
    ("Worship Script -  8.11.2020.docx", 2020),
    ("random notes.docx", None),
])
def test_year_from_filename(name, year):
    assert b.year_from_filename(name) == year


# ---------- merge ----------

def _row(title, source, **kw):
    base = {"title": title, "artist": "", "source": source}
    base.update(kw)
    return base


def test_merge_dedupes_spelling_variants_and_keeps_best_artist():
    songs = b.merge([
        _row("Before the Throne of God Above", "scripts", year=2015),
        _row("BEFORE THE THRONE OF GOD ABOVE", "edgar"),
        _row("Before The Throne Of God Above", "library", artist="Shane & Shane"),
        _row("Before the Throne of God Above", "scripts", artist="Hillsong", year=2019),
    ])
    assert len(songs) == 1
    s = songs[0]
    assert s["artist"] == "Shane & Shane"          # library beats scripts
    assert s["sources"] == ["edgar", "library", "scripts"]
    assert (s["first_year"], s["last_year"]) == (2015, 2019)


def test_scripts_only_single_word_once_is_not_trusted():
    one_word = b.merge([_row("Robots", "scripts")])[0]
    two_words = b.merge([_row("Relentless Love", "scripts")])[0]
    seen_twice = b.merge([_row("Hope", "scripts"), _row("Hope", "scripts")])[0]
    assert not b.trusted(one_word)
    assert b.trusted(two_words)
    assert b.trusted(seen_twice)


def test_decide_holds_scripts_heading_when_spotify_title_differs():
    songs = b.merge([_row("Relentless Love", "scripts")])
    songs[0]["match"] = {"uri": "u1", "name": "Relentless", "artist": "Hillsong",
                         "album": "x", "confidence": "medium"}
    b.decide(songs)
    assert songs[0]["status"] == "held"


def test_decide_flags_duplicate_recordings():
    songs = b.merge([_row("Oceans", "main"), _row("Oceans Where Feet May Fail", "edgar")])
    # Different canon keys, same Spotify recording -> second one is a dupe.
    for s in songs:
        s["match"] = {"uri": "same", "name": "Oceans", "artist": "Hillsong UNITED",
                      "album": "x", "confidence": "medium"}
    b.decide(songs)
    assert sorted(s["status"] for s in songs) == ["dupe", "on"]


# ---------- catalogue facets: every song lands in exactly ONE bucket ----------

SAMPLE = [
    {"title": "His Glory and My Good", "artist": "CityAlight", "count": 11,
     "last_sung": "2026-08-02", "first_year": 2022, "stream": "reformed-modern",
     "era": "Contemporary", "theme": "Praise", "pace": "Fast", "kids": False,
     "release_year": 2021, "chart_key": "D", "status": "on", "popularity": 45},
    {"title": "Amazing Grace", "artist": "", "count": 0, "last_sung": "",
     "first_year": 2014, "stream": "", "era": "", "theme": "", "pace": "",
     "kids": False, "release_year": None, "key": "", "status": "held", "popularity": None},
    {"title": "W-I-S-D-O-M", "artist": "Awesome Cutlery", "count": 5,
     "last_sung": "2025-01-05", "first_year": None, "stream": "kids-awesome-cutlery",
     "era": "", "theme": "Edify", "pace": "medium", "kids": True,
     "release_year": 2012, "chart_key": "G", "status": "on", "popularity": 10},
]
TODAY = "2026-10-21"


@pytest.mark.parametrize("facet", c.FACETS, ids=lambda f: f["id"])
def test_every_facet_is_mece(facet):
    for song in SAMPLE:
        value = facet["fn"](song, TODAY)
        assert value in facet["buckets"], (facet["id"], song["title"], value)


def test_facet_ids_unique_and_many():
    ids = [f["id"] for f in c.FACETS]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 15


def test_frequency_bands():
    f = c.facet("frequency")
    assert f["fn"](SAMPLE[0], TODAY) == "Staple (8+)"
    assert f["fn"](SAMPLE[2], TODAY) == "Regular (4–7)"
    assert f["fn"](SAMPLE[1], TODAY) == "Not sung 2024–26"


def test_recency_bands():
    f = c.facet("recency")
    assert f["fn"](SAMPLE[0], TODAY) == "Last 6 months"
    assert f["fn"](SAMPLE[2], TODAY) == "18+ months ago"
    assert f["fn"](SAMPLE[1], TODAY) == "Not since 2024"


def test_era_falls_back_to_stream_and_release_year():
    f = c.facet("era")
    assert f["fn"](SAMPLE[0], TODAY) == "Contemporary (2010+)"
    assert f["fn"]({**SAMPLE[1], "stream": "hymn-traditional"}, TODAY) == "Hymn"
    assert f["fn"]({**SAMPLE[1], "release_year": 2004}, TODAY) == "Classic (1990s–2000s)"


def test_region_from_artist():
    f = c.facet("region")
    assert f["fn"](SAMPLE[0], TODAY) == "Australia"
    assert f["fn"]({**SAMPLE[0], "artist": "Keith & Kristyn Getty"}, TODAY) == "UK & Ireland"
    assert f["fn"]({**SAMPLE[0], "artist": "Chris Tomlin"}, TODAY) == "USA"


def test_tradition_buckets_artists():
    f = c.facet("tradition")
    assert f["fn"](SAMPLE[0], TODAY) == "Reformed modern"
    assert f["fn"]({**SAMPLE[0], "stream": "", "artist": "Bethel Music"}, TODAY) == "Charismatic / CCM"


# ---------- AI tags + recording details ----------

def test_apply_ai_tags_fills_gaps_only_and_flags_non_songs():
    songs = b.merge([_row("Relentless Love", "scripts"), _row("Mitch Notes", "scripts"),
                     _row("Undivided", "main", extra={"theme": "Edify", "pace": "Slow"})])
    tags = {"Relentless Love": {"theme": "Assurance", "pace": "Fast", "not_a_song": False},
            "Mitch Notes": {"theme": "Praise", "pace": "Slow", "not_a_song": True},
            "Undivided": {"theme": "Praise", "pace": "Fast", "not_a_song": False}}
    b.apply_ai_tags(songs, tags)
    by = {s["title"]: s for s in songs}
    assert c.f_theme(by["Relentless Love"], TODAY) == "Assurance"
    assert c.f_theme(by["Undivided"], TODAY) == "Edify"      # Eric's own tag wins
    assert by["Mitch Notes"]["not_a_song"] is True
    b.decide(songs)
    assert by["Mitch Notes"]["status"] == "held"


def test_release_year_parses_spotify_dates():
    assert b.release_year("2019-03-01") == 2019
    assert b.release_year("1998") == 1998
    assert b.release_year("") is None


def test_catalogue_excludes_non_songs():
    songs = [dict(SAMPLE[0], key="a", sources=["main"]),
             dict(SAMPLE[1], key="b", sources=["scripts"], not_a_song=True)]
    assert [s["title"] for s in c.catalogue_songs(songs)] == ["His Glory and My Good"]


def test_ai_artists_only_fill_blanks():
    songs = b.merge([_row("Hear Our Praises", "scripts"),
                     _row("Undivided", "main", artist="Emu Music")])
    b.apply_ai_artists(songs, {"Hear Our Praises": {"artist": "Hillsong Worship", "confident": True},
                               "Undivided": {"artist": "Someone Else", "confident": True}})
    by = {s["title"]: s for s in songs}
    assert by["Hear Our Praises"]["artist"] == "Hillsong Worship"
    assert by["Hear Our Praises"]["artist_source"] == "ai"
    assert by["Undivided"]["artist"] == "Emu Music"


def test_ai_artists_skip_unconfident():
    songs = b.merge([_row("Mystery Tune", "scripts")])
    b.apply_ai_artists(songs, {"Mystery Tune": {"artist": "Guess Band", "confident": False}})
    assert songs[0]["artist"] == ""


def test_catalogue_folds_dupes_into_the_kept_song():
    kept = {"title": "Beautiful Saviour", "key": "k1", "sources": ["main"], "status": "on",
            "count": 3, "last_sung": "2025-01-05", "script_uses": 2, "first_year": 2016,
            "last_year": 2025, "match": {"uri": "u"}}
    dupe = {"title": "Beautiful Savior", "key": "k2", "sources": ["edgar", "scripts"], "status": "dupe",
            "count": 2, "last_sung": "2026-03-01", "script_uses": 4, "first_year": 2014,
            "last_year": 2026, "match": {"uri": "u"}}
    out = c.catalogue_songs([kept, dupe])
    assert len(out) == 1
    s = out[0]
    assert (s["count"], s["last_sung"], s["script_uses"]) == (5, "2026-03-01", 6)
    assert (s["first_year"], s["last_year"]) == (2014, 2026)
    assert s["sources"] == ["edgar", "main", "scripts"]


def test_chart_key_survives_merge():
    songs = b.merge([_row("Mighty to Save", "library", extra={"chart_key": "G", "has_chart": True})])
    assert c.f_key(songs[0], TODAY) == "G"


def test_region_for_unmapped_hymn_writer_and_new_artists():
    f = c.facet("region")
    hymn = {**SAMPLE[1], "artist": "Fanny Crosby", "stream": "hymn-traditional"}
    assert f["fn"](hymn, TODAY) == "Historic hymn writers"
    assert f["fn"]({**SAMPLE[0], "artist": "Maranatha! Music"}, TODAY) == "USA"
    assert f["fn"]({**SAMPLE[0], "artist": "City Harvest Church"}, TODAY) == "Singapore & local"
    assert f["fn"]({**SAMPLE[0], "artist": "Jonny Robinson, Rich Thompson"}, TODAY) == "Australia"
