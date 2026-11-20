from pathlib import Path

templates = [
    ("tmpl-char_sutradhar_narrator", Path("assets/svg/characters/sutradhar_narrator.svg")),
    ("tmpl-char_ravana", Path("assets/svg/characters/ravana.svg")),
    ("tmpl-bg_deep_cosmos_nebula", Path("assets/svg/backdrops/deep_cosmos_nebula.svg")),
    ("tmpl-bg_mount_kailash", Path("assets/svg/backdrops/mount_kailash.svg")),
    ("tmpl-bg_ancient_temple_ruins", Path("assets/svg/backdrops/ancient_temple_ruins.svg")),
    ("tmpl-diag_black_hole_anatomy", Path("assets/svg/diagrams/black_hole_anatomy.svg")),
    ("tmpl-diag_gravitational_time_dilation_clock", Path("assets/svg/diagrams/gravitational_time_dilation_clock.svg")),
    ("tmpl-diag_kailash_axis_alignments", Path("assets/svg/diagrams/kailash_axis_alignments.svg")),
]

html_parts = []
html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1080, height=1920, initial-scale=1.0">
  <title>Sutradhar Shorts Composition</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <!-- Master Composition Root (1080x1920 @ 30fps) - Clean-Canvas Edition -->
  <div id="root" data-composition-id="main" class="composition" data-fps="30" data-width="1080" data-height="1920" data-duration="45">
    <!-- Inline SVG Filter Graphs -->
    <svg style="position: absolute; width: 0; height: 0; overflow: hidden;" aria-hidden="true">
      <defs>
        <!-- Divine Bloom Filter -->
        <filter id="divine-bloom" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <!-- Fire Haze Filter -->
        <filter id="fire-haze" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.04 0.08" numOctaves="2" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="12" xChannelSelector="R" yChannelSelector="G" />
        </filter>

        <!-- Parchment Grain Filter -->
        <filter id="parchment-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" result="noise" />
          <feColorMatrix type="matrix" values="0 0 0 0 0.8  0 0 0 0 0.7  0 0 0 0 0.5  0 0 0 0.15 0" />
          <feComposite in="SourceGraphic" in2="noise" operator="arithmetic" k1="0" k2="1" k3="0.2" k4="0" />
        </filter>

        <!-- Cosmic Glow Filter -->
        <filter id="cosmic-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="14" result="glow" />
          <feMerge>
            <feMergeNode in="glow" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    </svg>

    <!-- Synchronous SVG Asset Store (Instant Preload, Zero Async Latency) -->
    <div id="svg-asset-store" style="display: none;">""")

for tmpl_id, svg_path in templates:
    svg_content = svg_path.read_text(encoding="utf-8")
    html_parts.append(f'    <template id="{tmpl_id}">\n{svg_content}\n    </template>')

html_parts.append("""    </div>

    <!-- Scene Container (Clips mounted here) -->
    <div id="scene-container" class="layer-fullscreen"></div>

    <!-- Frame-Locked FX Canvas (Particles) -->
    <canvas id="fx-canvas" width="1080" height="1920" class="layer-fullscreen" data-layout-allow-overflow="true" data-layout-ignore="true"></canvas>
  </div>

  <!-- Dependencies & Core Engine -->
  <script src="build/manifest.js"></script>
  <script src="assets/js/gsap.min.js"></script>
  <script src="assets/js/DrawSVGPlugin.min.js"></script>
  <script src="engine.js"></script>
</body>
</html>
""")

Path("index.html").write_text("\n".join(html_parts), encoding="utf-8")
print("index.html written successfully! Total size:", Path("index.html").stat().st_size)
