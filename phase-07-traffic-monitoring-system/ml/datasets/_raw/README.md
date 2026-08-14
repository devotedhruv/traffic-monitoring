# Raw dataset storage

Create imports only through the scripts where practical. Raw content is immutable input: normalization,
class remapping, splitting, and merges must write to a different directory.

Expected categories are `vehicles/`, `plates/`, `helmets/`, `plate_chars/`, and `own_nepal/`. All real
content below this directory is Git-ignored. `plate_chars` is OCR preparation data and must never be mixed
into the `plates` object-detection dataset.
