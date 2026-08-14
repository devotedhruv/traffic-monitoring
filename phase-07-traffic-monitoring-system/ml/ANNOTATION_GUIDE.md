# SadakDrishti annotation guide

Use CVAT, Roboflow, Label Studio, or another YOLO-compatible tool. No commercial annotation platform is
required. Export **YOLO object detection**, where each row is:

```text
class_id x_center y_center width height
```

Coordinates are normalized to `0.0–1.0`. Every intentional negative image needs an empty same-stem label.
Review validation and fixed-test labels independently. The longer policy in
[`ANNOTATION_GUIDELINES.md`](ANNOTATION_GUIDELINES.md) remains authoritative.

## Canonical classes

- Vehicle: `0 person`, `1 bicycle`, `2 car`, `3 motorcycle`, `4 bus`, `5 truck`.
- Plate detector: `0 license_plate` only. It locates the visible plate; it does not read characters.
- Helmet: `0 helmet`, `1 no_helmet`, primarily on rider/passenger head or upper-body ROIs compatible with
  production inference.

Tight boxes must describe visible evidence. Include partial objects when recognizable and difficult but
valid small objects. Do not label shadows, reflections, signboards, or ambiguous fragments.

For vehicles, review motorcycle/bicycle, bus/truck, and car/van-like ambiguity. `Van`, `Rickshaw`, and
`Auto` are not silently mapped to `car`; create an explicit reviewed mapping or ignore them.

For Nepal plates, cover front/rear, old/new styles, Latin/Devanagari, tilted, dirty, glare, partial
occlusion, distance, low light, blur, and compression. Box only the physical plate surface.

For helmets, cover full/half/open-face styles, riders and passengers, viewpoints and occlusion. Add hard
negatives for caps, hats, hoods, hair, scarves, bags, reflections, dark head regions, and circular
background objects. If the head is not sufficiently visible, do not infer a label.

## Export/import

Export images, labels, and dataset YAML. Then import the untouched export:

```bash
python ml/scripts/import_local.py \
  --input /path/to/cvat-or-label-tool-export.zip \
  --type plate \
  --source-name own-nepal-plates-v1 \
  --license PROPRIETARY-AUTHORIZED
```

Normalize and remap into a different directory; never edit raw imports in place.

