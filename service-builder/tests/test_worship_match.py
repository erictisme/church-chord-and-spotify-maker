"""Matcher ranking: real recordings beat piano/soaking/cover versions."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import worship_match as wm  # noqa: E402


def track(name, artist, album, pop=10, uri=None):
    return {"name": name, "uri": uri or f"spotify:track:{artist}-{album}".replace(" ", ""),
            "artists": [{"name": artist}], "album": {"name": album}, "popularity": pop}


class FakeSpotify:
    def __init__(self, tracks):
        self.tracks = tracks

    def search(self, q, type, limit):
        return {"tracks": {"items": self.tracks}}


def test_piano_and_soaking_albums_are_rejected():
    sp = FakeSpotify([
        track("Your Name", "YoungMin You", "Quiet Time Piano Worship", pop=60),
        track("Mighty Fortress", "Better Country Soaking", "Abundant Life", pop=60),
        track("My hope is in You", "Chill Worship", "Modern Jazz Worship Volume One", pop=60),
        track("Waiting Here for You", "Josh Snodgrass", "Worship Guitar, Vol. 2", pop=60),
        track("God of All My Days", "Heavenly Vocals", "Calming Worship Playlist for Prayer", pop=60),
    ])
    for title in ["Your Name", "Mighty Fortress", "My Hope Is In You",
                  "Waiting Here For You", "God Of All My Days"]:
        assert wm.find(sp, title) is None, title


def test_named_worship_artist_beats_generic_worship_cover():
    sp = FakeSpotify([
        track("Hear Our Praises", "Joshua David Harris", "Songs of Worship (1990s), Vol. 2", pop=40),
        track("Hear Our Praises", "Hillsong Worship", "Shout to the Lord", pop=20),
    ])
    assert wm.find(sp, "Hear Our Praises")["artist"] == "Hillsong Worship"


def test_known_artist_still_wins_and_is_high():
    sp = FakeSpotify([
        track("Mighty to Save", "Hillsong Worship", "Mighty to Save", pop=50),
        track("Mighty to Save", "The Worship Initiative", "The Worship Initiative, Vol. 7", pop=60),
    ])
    m = wm.find(sp, "Mighty To Save", "Hillsong")
    assert (m["artist"], m["confidence"]) == ("Hillsong Worship", "high")


def test_composer_credit_does_not_pull_in_classical_piano():
    sp = FakeSpotify([
        track("Blessed Assurance", "Fanny Crosby", "Piano Devotions: Hymns & Sacred Songs in Classical Settings", pop=50),
        track("Joy to the World", "George Frideric Handel", "Chamber Orchestra Christmas", pop=50),
        track("As the Deer", "Martin Nystrom", "Classic Hymns on Guitar", pop=50),
        track("Blessed Assurance", "Shane & Shane", "Hymns, Vol. 1", pop=30),
    ])
    assert wm.find(sp, "Blessed Assurance", "Fanny Crosby")["artist"] == "Shane & Shane"
    assert wm.find(sp, "Joy to the World", "Handel") is None
    assert wm.find(sp, "As the Deer", "Martin Nystrom") is None


def test_roster_original_artists_count_as_worship():
    sp = FakeSpotify([track("Where O Grave Is Your Victory?", "Ben Slee", "Where O Grave Is Your Victory?", pop=5)])
    assert wm.find(sp, "Where, O Grave, Is Your Victory")["confidence"] in ("high", "medium")
