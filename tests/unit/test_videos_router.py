import pytest
from pathlib import Path
import src.routers.videos_router as vr


class FakeTrack:
    def __init__(self, track_type, duration=None, width=None, height=None):
        self.track_type = track_type
        self.duration = duration
        self.width = width
        self.height = height


class FakeMediaInfo:
    def __init__(self, tracks):
        self.tracks = tracks


def test__video_info_with_video_track(monkeypatch, tmp_path):
    # Simula MediaInfo con una pista de video
    fake_tracks = [FakeTrack('Video', duration=30000, width='1920', height='1080')]
    monkeypatch.setattr(vr, 'MediaInfo', type('M', (), {'parse': lambda p: FakeMediaInfo(fake_tracks)}))

    duration, w, h = vr._video_info(Path('dummy.mp4'))
    assert duration == pytest.approx(30.0)
    assert w == 1920
    assert h == 1080


def test__video_info_no_video_track(monkeypatch, tmp_path):
    # Simula MediaInfo sin pistas de video
    fake_tracks = [FakeTrack('Audio', duration=None)]
    monkeypatch.setattr(vr, 'MediaInfo', type('M', (), {'parse': lambda p: FakeMediaInfo(fake_tracks)}))

    duration, w, h = vr._video_info(Path('dummy.mp4'))
    assert duration == pytest.approx(0.0)
    assert w == 0
    assert h == 0
