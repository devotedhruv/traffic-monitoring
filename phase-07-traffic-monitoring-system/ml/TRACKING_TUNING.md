# ByteTrack tuning and evaluation

ByteTrack is an association algorithm and does not require supervised model training. SadakDrishti keeps
its production values in `config/live_bytetrack.yaml`; do not change them randomly or tune on one clip.

- `track_high_thresh`: confidence required for the first high-quality association pass. Raising it reduces
  weak matches but can miss distant/occluded vehicles.
- `track_low_thresh`: lower bound for the second association pass. Lower values can recover occluded
  objects but may attach background detections.
- `new_track_thresh`: confidence required to create a new ID. Too low creates duplicates; too high delays
  or misses tracks.
- `track_buffer`: frames retained after a detection disappears. Increase for longer occlusion, balanced
  against incorrect reattachment and memory.
- `match_thresh`: association-matching threshold. Test deliberately; the effective trade-off depends on
  detector quality, frame rate, traffic density, and camera motion.

Build a fixed tracking benchmark with ground-truth object IDs across normal traffic, congestion, crossings,
partial/full occlusion, stopped traffic, and re-entry. Measure ID switches, fragmented/lost tracks, duplicate
tracks, recovery after long occlusion, and track duration. Test at the actual production FPS and detector
confidence. Change one parameter at a time, record the configuration and benchmark, and re-check speed,
plate voting, and violation correlation because all depend on stable track IDs.

