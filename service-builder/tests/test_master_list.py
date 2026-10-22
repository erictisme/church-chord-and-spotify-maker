"""Tests for the FMH master list + catalogue. Run: python3 -m pytest service-builder/tests"""

import json
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
    ("All the way my saviour leads me - Chris Tomlin", "All the way my saviour leads me", "Chris Tomlin"),
    ("Mercy Matt Redman", "Mercy", "Matt Redman"),
    ("Brenton Brown - Jesus Take All Of Me (Just As I Am)", "Jesus Take All Of Me", "Brenton Brown"),
    ("Trust and Obey Don Moen", "Trust and Obey", "Don Moen"),
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


# ---------- who picked it + per-year analytics ----------

def test_scripts_spec_parses_owner_and_edgar_subfolder_override():
    assert b.parse_scripts_spec("Rizvan=/x/Scripts") == ("Rizvan", "/x/Scripts")
    assert b.parse_scripts_spec("/x/eric-all-weeks") == ("", "/x/eric-all-weeks")
    assert b.owner_for("Rizvan", "/x/Scripts/Edgar/Worship 8.11.2020.docx") == "Edgar"
    assert b.owner_for("Rizvan", "/x/Scripts/2014-01-04 Worship.docx") == "Rizvan"


def test_merge_counts_owners_and_years():
    songs = b.merge([
        _row("Cornerstone", "scripts", owner="Rizvan", year=2015),
        _row("Cornerstone", "scripts", owner="Rizvan", year=2016),
        _row("Cornerstone", "scripts", owner="Eric", year=2016),
        _row("Cornerstone", "history", count=2, last_sung="2025-03-01", local=False, kids=False,
             dates=["2024-08-01", "2025-03-01"]),
    ])
    s = songs[0]
    assert s["owners"] == {"Rizvan": 2, "Eric": 1}
    assert s["year_counts"] == {"2015": 1, "2016": 2, "2024": 1, "2025": 1}


def test_parse_leader_csv_finds_date_and_known_name(tmp_path):
    p = tmp_path / "roster.csv"
    p.write_text("Date,Service leader,Music\n4 Jan 2026,Eric Tan,Riz\n11/01/2026,Rizvan,Edgar\n,,\nfoo,bar,baz\n")
    assert b.parse_leader_csv(str(p)) == {"2026-01-04": "Eric", "2026-01-11": "Rizvan"}


def test_chart_data_top_hits_per_person_and_tradition_by_year():
    songs = [
        {**SAMPLE[0], "key": "a", "sources": ["main"], "owners": {"Eric": 5, "Rizvan": 1},
         "year_counts": {"2016": 2, "2025": 3}, "roster_leaders": {"Eric": 2}},
        {**SAMPLE[2], "key": "b", "sources": ["main"], "owners": {"Rizvan": 4},
         "year_counts": {"2016": 1}},
    ]
    data = c.chart_data(songs, TODAY)
    assert data["people"]["Eric"][0] == {"t": "His Glory and My Good", "n": 7}
    assert data["people"]["Rizvan"][0]["t"] == "W-I-S-D-O-M"
    assert data["by_year"]["2016"] == {"Reformed modern": 1, "Kids": 1}
    assert data["top_sung"][0]["t"] == "His Glory and My Good"


def test_dupe_fold_sums_owners_and_years():
    kept = {"title": "A", "key": "k1", "sources": ["main"], "status": "on", "match": {"uri": "u"},
            "owners": {"Eric": 2}, "year_counts": {"2016": 1}}
    dupe = {"title": "A Two", "key": "k2", "sources": ["scripts"], "status": "dupe", "match": {"uri": "u"},
            "owners": {"Eric": 1, "Rizvan": 3}, "year_counts": {"2016": 2, "2017": 1}}
    s = c.catalogue_songs([kept, dupe])[0]
    assert s["owners"] == {"Eric": 3, "Rizvan": 3}
    assert s["year_counts"] == {"2016": 3, "2017": 1}


def test_song_counts_once_per_script(tmp_path, monkeypatch):
    (tmp_path / "2016-01-10 Worship.docx").write_bytes(b"")
    monkeypatch.setattr(b, "script_headings", lambda path: ["Still", "Still", "Forever"])
    rows = list(b.from_scripts([f"Rizvan={tmp_path}"]))
    assert sorted(r["title"] for r in rows) == ["Forever", "Still"]
    assert all(r["owner"] == "Rizvan" and r["year"] == 2016 for r in rows)


def test_same_service_in_script_and_roster_is_not_double_counted():
    songs = b.merge([
        _row("Undivided", "scripts", owner="Eric", year=2025),
        _row("Undivided", "history", count=2, last_sung="2025-09-06", local=False, kids=False,
             dates=["2025-04-27", "2025-09-06"]),
    ])
    assert songs[0]["year_counts"]["2025"] == 2      # max(script 1, roster 2), not 3


def _song(title, years, trad_stream="reformed-modern", count=0):
    return {**SAMPLE[0], "title": title, "key": title, "sources": ["main"], "stream": trad_stream,
            "count": count, "year_counts": years, "owners": {}}


def test_year_top_evergreens_and_gone_quiet():
    songs = [
        _song("Old Favourite", {"2016": 5, "2017": 4, "2018": 3}),
        _song("Evergreen", {str(y): 1 for y in range(2014, 2027)}),
        _song("New Hit", {"2025": 6, "2026": 4}, count=10),
        _song("Once", {"2016": 1}),
    ]
    d = c.chart_data(songs, TODAY)
    assert d["year_top"]["2016"][0] == {"t": "Old Favourite", "n": 5, "trad": "Reformed modern"}
    assert d["year_top"]["2025"][0]["t"] == "New Hit"
    assert d["evergreens"][0] == {"t": "Evergreen", "years": 13, "first": "2014", "last": "2026"}
    quiet = [r["t"] for r in d["gone_quiet"]]
    assert "Old Favourite" in quiet and "Once" not in quiet and "Evergreen" not in quiet


def test_songbook_numbers_each_book_alphabetically_and_rows_carry_history():
    songs = [
        _song("Be Thou My Vision", {"2016": 2}, trad_stream="hymn-traditional"),
        _song("Amazing Grace", {"2015": 1}, trad_stream="hymn-traditional"),
        _song("Undivided", {"2025": 3}),
    ]
    songs[2].update(dates=["2025-04-27"], owners={"Eric": 2}, sources=["history", "main"],
                    first_year=2025, last_year=2025)
    rows = {r["t"]: r for r in c.rows_for_page(songs, TODAY)}
    assert (rows["Amazing Grace"]["book"], rows["Amazing Grace"]["no"]) == ("Hymn & traditional", 1)
    assert rows["Be Thou My Vision"]["no"] == 2
    assert rows["Undivided"]["no"] == 1
    h = rows["Undivided"]["h"]
    assert h["years"] == {"2025": 3} and h["dates"] == ["2025-04-27"] and h["who"] == {"Eric": 2}
    assert h["src"] == ["history", "main"]


def test_hymn_writer_is_not_used_as_search_artist():
    hymn = {"title": "Here Is Love", "artist": "William Rees", "stream": "hymn-traditional", "era": ""}
    modern = {"title": "Undivided", "artist": "Emu Music", "stream": "reformed-modern", "era": ""}
    named_hymn = {"title": "Be Thou My Vision", "artist": "Indelible Grace", "stream": "hymn-traditional", "era": ""}
    assert b.search_artist(hymn) == ""
    assert b.search_artist(modern) == "Emu Music"
    assert b.search_artist(named_hymn) == "Indelible Grace"


def test_overrides_pin_a_recording():
    songs = b.merge([_row("Our God Is An Awesome God", "edgar")])
    songs[0]["match"] = {"uri": "wrong", "name": "x", "artist": "Opwekking", "album": "y", "confidence": "medium"}
    b.apply_overrides(songs, {"Our God Is An Awesome God": {"uri": "spotify:track:abc",
                                                            "artist": "Rich Mullins", "name": "Awesome God"}})
    m = songs[0]["match"]
    assert (m["uri"], m["confidence"]) == ("spotify:track:abc", "high")


def test_cached_match_failing_current_rules_is_searched_again(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"How Deep the Father's Love|Stuart Townend": {
        "uri": "old", "name": "How Deep the Father's Love", "artist": "Stuart Townend",
        "album": "String Heaven", "confidence": "high"}}))
    monkeypatch.setattr(b, "CACHE", str(cache))
    calls = []
    def fake_find(sp, title, artist=""):
        calls.append(title)
        return {"uri": "new", "name": title, "artist": "Stuart Townend", "album": "Monument", "confidence": "high"}
    monkeypatch.setattr(b.cmp.worship_match, "find", fake_find)
    song = {"title": "How Deep the Father's Love", "artist": "Stuart Townend", "stream": "", "era": ""}
    b.match_all(None, [song])
    assert calls == ["How Deep the Father's Love"] and song["match"]["uri"] == "new"


# ---------- mashups, keys, originals, vitality ----------

@pytest.mark.parametrize("heading, parts", [
    ("WHO AM I / LOVE CAME DOWN", ["Who Am I", "Love Came Down"]),
    ("OPEN THE EYES OF MY HEART x HOLY HOLY HOLY (C)", ["Open The Eyes Of My Heart", "Holy Holy Holy"]),
    ("A BROKEN SPIRIT (E1) & ISN'T HE? (A22)", ["A Broken Spirit", "Isn't He?"]),
    ("MEDLEY - THERE IS A FOUNTAIN / NOTHING BUT THE BLOOD", ["There Is A Fountain", "Nothing But The Blood"]),
    ("Bridge x 2", None),
    ("Mighty to Save (G)", None),
])
def test_split_mashup(heading, parts):
    assert b.split_mashup(heading) == parts


def test_mashups_need_known_songs_and_skip_alt_titles():
    rows = [
        _row("Who Am I", "main"), _row("Love Came Down", "main"), _row("Burn for You", "main"),
        _row("My Hope Is Built", "main"), _row("The Solid Rock", "main"),
    ]
    songs = b.merge(rows)
    raw = [(["Who Am I", "Love Came Down"], 2016, "Rizvan"), (["Who Am I", "Love Came Down"], 2018, "Eric"),
           (["Burn for You", "Robots"], 2019, "Eric"), (["My Hope Is Built", "The Solid Rock"], 2025, "")]
    out = b.build_mashups(raw, songs)
    assert out == [{"songs": ["Who Am I", "Love Came Down"], "n": 2, "years": [2016, 2018], "who": {"Rizvan": 1, "Eric": 1}}]


@pytest.mark.parametrize("heading, after, key", [
    ("Mighty to Save (G)", ["Verse 1", "G  D  Em  C"], "G"),
    ("Same Love [Capo 2]", ["Intro", "G  C  G  D"], "A"),
    ("Father (CAPO -1)", ["E   B   C#m  A"], "Eb"),
    ("Still", ["Verse", "Bb  Eb  F"], "Bb"),
    ("Your Grace Is Enough", ["Intro: E    E/G#     A2"], "E"),
    ("Welcome", ["Good morning church"], ""),
])
def test_detect_key_from_heading_capo_and_first_chord(heading, after, key):
    assert b.detect_key(heading, after) == key


def test_originals_mark_songs_local():
    songs = b.merge([_row("For You Alone", "history", count=1, last_sung="2025-06-08", local=False,
                          kids=False, dates=["2025-06-08"]), _row("Undivided", "main")])
    b.apply_originals(songs, ["For You Alone", "More Than I Can Bear"])
    by = {s["title"]: s for s in songs}
    assert by["For You Alone"]["local"] and not by["Undivided"]["local"]


def test_people_by_year_and_vitality():
    songs = [
        {**_song("Cornerstone", {"2016": 2, "2025": 1}, trad_stream="charismatic-ccm"),
         "owner_years": {"Rizvan": {"2016": 2}, "Eric": {"2025": 1}}, "first_year": 2016},
        {**_song("Undivided", {"2025": 3}), "owner_years": {"Eric": {"2025": 3}}, "first_year": 2025},
        {**_song("Father", {"2018": 1}, trad_stream="local-original"), "local": True,
         "owner_years": {"Eric": {"2018": 1}}, "first_year": 2018},
    ]
    mashups = [{"songs": ["Cornerstone", "Undivided"], "n": 1, "years": [2025], "who": {"Eric": 1}}]
    d = c.chart_data(songs, TODAY, mashups=mashups)
    assert d["people_by_year"]["Eric"]["2025"][0] == {"t": "Undivided", "n": 3}
    assert d["people_by_year"]["Rizvan"]["2016"][0]["t"] == "Cornerstone"
    v = d["vitality"]
    assert v["2025"]["songs"] == 2 and v["2025"]["new"] == 1 and v["2025"]["mashups"] == 1
    assert v["2018"]["originals"] == 1
    assert 0 <= v["2025"]["balance"] <= 100


def test_keys_flow_to_songbook_and_key_facet():
    s = {**_song("Still", {"2016": 2}), "keys_played": {"Bb": 3, "A": 1}, "latest_key": "A", "chart_key": ""}
    row = c.rows_for_page([s], TODAY)[0]
    assert row["h"]["keys"] == {"Bb": 3, "A": 1} and row["h"]["latest_key"] == "A"
    assert c.f_key(s, TODAY) == "A"            # latest key played wins over no chart
    assert c.f_key({**s, "latest_key": "", "chart_key": "G"}, TODAY) == "G"


def test_edgar_medley_files_split_into_songs(tmp_path):
    import zipfile as zf
    z = tmp_path / "e.zip"
    with zf.ZipFile(z, "w") as f:
        f.writestr("Master List - Edgar/Medley - Open the eyes of my heart & All hail the power.doc", "x")
        f.writestr("Master List - Edgar/Mighty to save (G).doc", "x")
    titles = sorted(r["title"] for r in b.from_edgar(str(z)))
    assert titles == ["All hail the power", "Mighty to save", "Open the eyes of my heart"]


def test_story_facts():
    songs = [
        _song("CCM A", {"2016": 3, "2017": 2}, trad_stream="charismatic-ccm"),
        _song("CCM B", {"2016": 1, "2021": 2, "2022": 1}, trad_stream="charismatic-ccm"),
        _song("Ref A", {"2021": 1, "2022": 4, "2023": 2}),
        _song("Ref B", {"2022": 1, "2023": 1}),
    ]
    for s, k in zip(songs, ["G", "G", "C", "G"]):
        s["latest_key"] = k
    st = c.chart_data(songs, TODAY)["story"]
    assert st["crossover_year"] == "2022"          # Reformed ahead from here on, every year
    assert st["quietest_year"] == "2017"
    assert st["top_key"] == ("G", 3)
    assert st["most_balanced_year"] in ("2016", "2017", "2021", "2022", "2023")
