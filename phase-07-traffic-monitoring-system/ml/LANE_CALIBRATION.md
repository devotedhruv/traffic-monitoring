# Lane and direction calibration

SadakDrishti currently uses calibrated ground-plane trajectories plus explicit lane rules. It does not use
lane segmentation, and administrators should not add segmentation until measured operational evidence
shows the rule-based approach cannot meet requirements.

## Administrator workflow

1. Calibrate the road quadrilateral with measured width/length for the specific camera.
2. Determine the lane count and map each physical lane to a normalized lateral interval (`minX`, `maxX`)
   across the calibrated road width. Current production rules use these stable intervals rather than an
   arbitrary image-space polygon.
3. Assign a unique positive `laneId` and a small `boundaryTolerance` to reduce boundary jitter.
4. Set `allowedVehicleTypes` from `bicycle`, `car`, `motorcycle`, `bus`, and `truck`; an empty list allows all.
5. Set `allowedDirection` to exactly one of `approaching`, `moving_away`, `left_to_right`, `right_to_left`,
   or `both`.
6. Configure and verify the global `TRAFFIC_SPEED_LIMIT`. The current schema does **not** implement a
   different speed limit per lane; do not describe one as enforced until the database, API, runtime, and UI
   are extended together.
7. Save rules through the existing camera lane-settings API/UI and test representative trajectories.

Lane intervals must not overlap. Use stable observations, minimum travel distance, a grace period, and
multiple confirmations to avoid violations during lane changes or on boundaries. Validate approaching and
departing traffic separately, then review wrong-lane/wrong-direction evidence for false alerts caused by
camera geometry, occlusion, or track switches.

