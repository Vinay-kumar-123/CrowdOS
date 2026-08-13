import pytest
from tracking.models.bytetrack import ByteTrackTracker
from tracking.results.schema import TrackState
from tracking.tests.conftest import make_detection_result


def test_bytetrack_creation_and_update():
    """
    Test track creation on frame 1 and track position update on frame 2.
    """
    tracker = ByteTrackTracker(track_thresh=0.5, camera_id="cam_test")

    # Frame 1: High confidence detection
    det_f1 = make_detection_result(1, "cam_test", [(100, 100, 200, 300, 0.90)])
    res_f1 = tracker.update(det_f1)

    assert len(res_f1.tracks) == 1
    track_f1 = res_f1.tracks[0]
    first_track_id = track_f1.track_id
    assert track_f1.confidence == 0.90
    assert track_f1.track_state == TrackState.ACTIVE

    # Frame 2: Slightly shifted detection
    det_f2 = make_detection_result(2, "cam_test", [(105, 105, 205, 305, 0.92)])
    res_f2 = tracker.update(det_f2)

    assert len(res_f2.tracks) == 1
    track_f2 = res_f2.tracks[0]
    assert track_f2.track_id == first_track_id  # Persistent Track ID maintained
    assert track_f2.frame_number == 2
    assert track_f2.track_state == TrackState.ACTIVE


def test_bytetrack_stage2_low_confidence_association():
    """
    Test 2nd stage data association: low-confidence detection matches active track during partial occlusion.
    """
    tracker = ByteTrackTracker(track_thresh=0.5, min_confidence=0.1, camera_id="cam_test")

    # Frame 1: High confidence detection creates track
    det_f1 = make_detection_result(1, "cam_test", [(100, 100, 200, 300, 0.85)])
    res_f1 = tracker.update(det_f1)
    track_id = res_f1.tracks[0].track_id

    # Frame 2: Low confidence detection (0.25 < track_thresh 0.5) at overlapping box
    det_f2 = make_detection_result(2, "cam_test", [(102, 102, 202, 302, 0.25)])
    res_f2 = tracker.update(det_f2)

    assert len(res_f2.tracks) == 1
    track_f2 = res_f2.tracks[0]
    assert track_f2.track_id == track_id  # Matched via 2nd stage low-confidence association
    assert track_f2.confidence == 0.25


def test_bytetrack_occlusion_and_recovery():
    """
    Test track loss when detection disappears (occlusion) and recovery when re-observed.
    Transitions: ACTIVE -> LOST -> REIDENTIFIED -> ACTIVE.
    """
    tracker = ByteTrackTracker(track_thresh=0.5, max_lost_frames=5, camera_id="cam_test")

    # Frame 1: Detection present
    det_f1 = make_detection_result(1, "cam_test", [(100, 100, 200, 300, 0.85)])
    res_f1 = tracker.update(det_f1)
    track_id = res_f1.tracks[0].track_id

    # Frame 2: Empty detection (person occluded)
    det_f2 = make_detection_result(2, "cam_test", [])
    res_f2 = tracker.update(det_f2)
    assert len(res_f2.tracks) == 0
    assert res_f2.total_lost_tracks == 1

    # Frame 3: Detection reappears at close location
    det_f3 = make_detection_result(3, "cam_test", [(104, 104, 204, 304, 0.88)])
    res_f3 = tracker.update(det_f3)

    assert len(res_f3.tracks) == 1
    track_f3 = res_f3.tracks[0]
    assert track_f3.track_id == track_id  # Track ID preserved after recovery
    assert tracker.total_reidentifications == 1


def test_bytetrack_expiration_after_max_lost_frames():
    """
    Test that lost track is permanently removed and expired after exceeding max_lost_frames.
    """
    tracker = ByteTrackTracker(track_thresh=0.5, max_lost_frames=3, camera_id="cam_test")

    # Frame 1: Detection creates track
    det_f1 = make_detection_result(1, "cam_test", [(100, 100, 200, 300, 0.85)])
    tracker.update(det_f1)

    # Frames 2 to 5: Empty frames (4 frames lost > max_lost_frames=3)
    for f in range(2, 6):
        det_empty = make_detection_result(f, "cam_test", [])
        tracker.update(det_empty)

    # On frame 5, lost track should be purged/expired
    stats = tracker.get_statistics()
    assert stats["lost_tracks_count"] == 0
    assert len(tracker.removed_stracks) >= 1
