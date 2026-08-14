# SadakDrishti annotation guidelines

Use a YOLO-compatible detection annotation tool and perform a second-person review on the fixed validation
and test sets. Boxes should be tight, consistent, and describe visible evidence—not assumptions.

## Vehicle dataset

Class IDs are fixed: `person`, `bicycle`, `car`, `motorcycle`, `bus`, `truck`. Tight boxes must contain the
visible object. Annotate partially visible objects when their class is still recognizable. Do not annotate
extremely ambiguous fragments, shadows, reflections, posters, or screen images. Do not skip obvious small
objects merely because they are difficult. Apply the same class policy to vans/minibuses before annotation;
do not silently invent a seventh class.

Review especially:

- bus-versus-truck and bicycle-versus-motorcycle consistency;
- people riding/in vehicles versus true pedestrians;
- objects cut by frame boundaries;
- crowded and heavily occluded objects;
- tiny distant road users.

## Nepal license-plate dataset

Use the single `license_plate` class. The detector locates plates only; it does not recognize text. Draw a
tight box around the actual visible plate surface, not the bumper or whole vehicle. Include Nepal-specific
old/new plate styles, Latin and Devanagari text, front/rear plates, tilted plates, small/distant plates,
partially occluded plates, recognizable blur, and low light. Do not label signboards, vehicle branding,
reflectors, or arbitrary rectangles as plates. Mark truly unreadable shapes only when the physical plate is
still visually identifiable—OCR readability is not the detector-label criterion.

## Helmet dataset

Use `helmet` and `no_helmet` around the rider/passenger head region in the same kind of ROI used by
SadakDrishti production inference. Cover drivers and passengers, full-face, half, and open-face helmets,
dark/bright helmets, different viewpoints, partial occlusion, and night scenes. If the head is not visible
enough to decide, do not infer a label.

Hard negatives are essential: caps, hats, hair, scarves, hoods, dark head regions, bags behind riders,
headlights, and reflections. Include reviewed examples that explicitly separate caps/hats from helmets.
Keep motorcycle context in the source image even when the training crop focuses on the rider/head ROI.

## Review checklist

- No missing obvious objects and no duplicated boxes.
- Correct class ID and consistent class meaning.
- Box edges do not extend outside the image.
- Boxes are neither loose nor clipped through the object.
- Negative images have an intentional empty label file.
- Frames from one source session retain the same split.
- Validation and fixed-test labels receive independent review.

