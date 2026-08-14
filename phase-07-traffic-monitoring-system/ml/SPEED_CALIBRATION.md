# Speed calibration and accuracy

Speed remains a calibrated geometric measurement, not a guessed AI output:

```text
bounding-box bottom center
        ↓
camera homography
        ↓
ground-plane coordinates in metres
        ↓
ByteTrack trajectory and timestamps
        ↓
distance / elapsed time × 3.6
        ↓
km/h with smoothing and outlier rejection
```

For every camera, physically measure at least two road dimensions and select four widely separated points
on one planar road surface. Enter their matching image/world points through the existing camera-calibration
workflow. Avoid points clustered together, different elevation planes, moving references, and guessed lane
widths. Preserve calibration per camera and re-calibrate after zoom, pan, resolution, or mounting changes.

Use media/capture timestamps rather than assuming displayed FPS. Require a minimum travel time/distance,
smooth noisy trajectories, and reject unrealistic speed/acceleration—the current `SpeedEstimator` already
implements these controls. Validate using multiple vehicles with independently known speed (radar/LIDAR,
surveyed timing gates, or another calibrated reference) across near/far road regions and lanes. Report bias,
mean absolute error, 95th-percentile error, and overspeed false-positive/false-negative rates. A detector
retrain does not replace camera-specific speed revalidation.

