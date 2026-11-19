# Derived logo sizes

Generated from [`../cogito-multicolor-transparent.svg`](../cogito-multicolor-transparent.svg) — the mark is the
same in every file here; only the canvas, the padding and the presence of the tagline differ.

| File | Size | Where it goes |
|---|---|---|
| `avatar-500.png` | 500×500 | GitHub repo avatar (Settings → General). The mark is padded to 82% so the circular mask never clips a lobe. |
| `favicon-32.png` | 32×32 | Browser tab / bookmark, where the app's SVG favicon is not used. |
| `favicon-64.png` | 64×64 | Retina tab, and any surface that wants a second icon size. |
| `social-preview-1280x640.png` | 1280×640 | GitHub social preview (Settings → General). Plate `#111726` — the app's own figure ground — with the tagline. |

The master SVG's `feDropShadow` filter is dropped for these renders: at icon sizes it produced a grey halo on
light backgrounds, and on the `#111726` plate it is invisible anyway.

Regenerate by rendering the master (shadowless) in a browser at 1024×1024 on a transparent canvas, trimming the
transparent margin, then padding and downsampling: 410×410 centred in 500 for the avatar, 88% of the canvas for
the favicons. The social card is the mark plus the name and tagline set in DejaVu Sans on the plate.
