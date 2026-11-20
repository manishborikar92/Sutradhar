import os
import shutil

video_dir = "build/benchmark_v2/video"
os.makedirs(os.path.join(video_dir, "assets", "js"), exist_ok=True)
shutil.copyfile("assets/js/gsap.min.js", os.path.join(video_dir, "assets", "js", "gsap.min.js"))

with open("build/benchmark_v2/ravana_v2.svg", "r", encoding="utf-8") as f:
    svg_content = f.read()

# Make sure the SVG scales and marks wrath sunburst with allow overflow
svg_inline = svg_content.replace('width="800" height="1200"', 'width="100%" height="100%" data-layout-allow-overflow="true"')
svg_inline = svg_inline.replace('id="wrath_sunburst" opacity="0"', 'id="wrath_sunburst" opacity="0" data-layout-allow-overflow="true"')

# Generate 18 floating ember elements with data-layout-ignore
ember_divs = "\\n".join([f'      <div class="ember" data-layout-ignore="true" style="width: {6 + (i%4)*3}px; height: {6 + (i%4)*3}px; left: {80 + (i*52)%920}px;"></div>' for i in range(18)])

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sutradhar v2 — Kathputli Benchmark</title>
  <link rel="stylesheet" href="styles.css">
  <script src="assets/js/gsap.min.js"></script>
</head>
<body data-composition-id="ravana_benchmark" data-width="1080" data-height="1920" data-duration="22.01">

  <!-- CAMERA STAGE FOR DETERMINISTIC GSAP PUSH-INS & SHAKES -->
  <div id="stage" data-layout-allow-overflow="true">

    <!-- THEATRICAL LANKA COURT ENVIRONMENT -->
    <div id="environment" data-layout-allow-overflow="true">
      <div class="temple-wall" data-layout-allow-occlusion="true" data-layout-ignore="true"></div>
      <div class="wall-texture" data-layout-allow-occlusion="true" data-layout-ignore="true"></div>

      <!-- Sandstone Pillars Left & Right -->
      <div class="pillar pillar-left" data-layout-allow-overflow="true">
        <div class="pillar-fluting"></div>
        <div class="pillar-capital"></div>
      </div>
      <div class="pillar pillar-right" data-layout-allow-overflow="true">
        <div class="pillar-fluting"></div>
        <div class="pillar-capital"></div>
      </div>

      <!-- Top Carved Temple Archway & Marigold Torans -->
      <div class="archway" data-layout-allow-overflow="true">
        <div class="arch-beam"></div>
        <!-- Toran Floral SVG -->
        <svg class="toran-garland" viewBox="0 0 1080 90" width="1080" height="90">
          <defs>
            <radialGradient id="marigold_yellow" cx="40%" cy="40%" r="60%">
              <stop offset="0%" stop-color="#fff066"/>
              <stop offset="60%" stop-color="#fcc419"/>
              <stop offset="100%" stop-color="#e67700"/>
            </radialGradient>
            <radialGradient id="marigold_orange" cx="40%" cy="40%" r="60%">
              <stop offset="0%" stop-color="#ff922b"/>
              <stop offset="60%" stop-color="#f76707"/>
              <stop offset="100%" stop-color="#d9480f"/>
            </radialGradient>
            <g id="flower_tassel">
              <path d="M 0 0 Q 30 35 60 0" stroke="#2b8a3e" stroke-width="3" fill="none"/>
              <circle cx="0" cy="5" r="9" fill="url(#marigold_yellow)"/>
              <circle cx="15" cy="18" r="8" fill="url(#marigold_orange)"/>
              <circle cx="30" cy="24" r="10" fill="url(#marigold_yellow)"/>
              <circle cx="45" cy="18" r="8" fill="url(#marigold_orange)"/>
              <circle cx="60" cy="5" r="9" fill="url(#marigold_yellow)"/>
              <polygon points="30,24 25,48 30,55 35,48" fill="#2b8a3e"/>
            </g>
          </defs>
          <use href="#flower_tassel" x="120" y="5"/>
          <use href="#flower_tassel" x="220" y="5"/>
          <use href="#flower_tassel" x="320" y="5"/>
          <use href="#flower_tassel" x="420" y="5"/>
          <use href="#flower_tassel" x="520" y="5"/>
          <use href="#flower_tassel" x="620" y="5"/>
          <use href="#flower_tassel" x="720" y="5"/>
          <use href="#flower_tassel" x="820" y="5"/>
        </svg>
      </div>

      <!-- Velvet Stage Curtains -->
      <div class="curtain curtain-left" data-layout-allow-overflow="true"></div>
      <div class="curtain curtain-right" data-layout-allow-overflow="true"></div>

      <!-- Left Fire Brazier / Diya -->
      <div class="brazier-podium brazier-left">
        <svg viewBox="0 0 160 240" width="160" height="240">
          <defs>
            <linearGradient id="brass_podium" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#ffd43b"/>
              <stop offset="50%" stop-color="#f59f00"/>
              <stop offset="100%" stop-color="#8c5800"/>
            </linearGradient>
            <radialGradient id="flame_glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#fff3bf"/>
              <stop offset="30%" stop-color="#ff922b"/>
              <stop offset="70%" stop-color="#e03131"/>
              <stop offset="100%" stop-color="#c92a2a" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <path d="M 40 230 L 120 230 L 105 150 L 55 150 Z" fill="url(#brass_podium)"/>
          <ellipse cx="80" cy="150" rx="55" ry="18" fill="url(#brass_podium)"/>
          <ellipse cx="80" cy="148" rx="48" ry="12" fill="#5c3800"/>
          <g id="flame_left" transform="translate(80, 142)">
            <ellipse cx="0" cy="-25" rx="35" ry="55" fill="url(#flame_glow)"/>
            <path d="M -22 0 Q -35 -45 0 -85 Q 35 -45 22 0 Z" fill="#ff922b"/>
            <path d="M -14 0 Q -22 -35 0 -65 Q 22 -35 14 0 Z" fill="#ffe066"/>
            <path d="M -6 0 Q -10 -25 0 -45 Q 10 -25 6 0 Z" fill="#ffffff"/>
          </g>
        </svg>
      </div>

      <!-- Right Fire Brazier / Diya -->
      <div class="brazier-podium brazier-right">
        <svg viewBox="0 0 160 240" width="160" height="240">
          <path d="M 40 230 L 120 230 L 105 150 L 55 150 Z" fill="url(#brass_podium)"/>
          <ellipse cx="80" cy="150" rx="55" ry="18" fill="url(#brass_podium)"/>
          <ellipse cx="80" cy="148" rx="48" ry="12" fill="#5c3800"/>
          <g id="flame_right" transform="translate(80, 142)">
            <ellipse cx="0" cy="-25" rx="35" ry="55" fill="url(#flame_glow)"/>
            <path d="M -22 0 Q -35 -45 0 -85 Q 35 -45 22 0 Z" fill="#ff922b"/>
            <path d="M -14 0 Q -22 -35 0 -65 Q 22 -35 14 0 Z" fill="#ffe066"/>
            <path d="M -6 0 Q -10 -25 0 -45 Q 10 -25 6 0 Z" fill="#ffffff"/>
          </g>
        </svg>
      </div>

      <!-- Royal Podium / Dais Base -->
      <div class="royal-dais" data-layout-allow-overflow="true">
        <div class="dais-trim"></div>
      </div>
    </div>

    <!-- MAIN CHARACTER KATHPUTLI RIG -->
    <div id="puppet_wrapper" data-layout-allow-overflow="true">
      {svg_inline}
    </div>

  </div>

  <!-- FLOATING WARM EMBER PARTICLES -->
  <div id="embers_container" data-layout-ignore="true" data-layout-allow-safe-zone="true">
{ember_divs}
  </div>

  <!-- THEATRICAL VIGNETTE OVERLAY -->
  <div id="vignette" data-layout-allow-occlusion="true" data-layout-ignore="true"></div>

  <!-- DRAMATIC WRATH FLASH OVERLAY -->
  <div id="wrath_flash" data-layout-allow-occlusion="true" data-layout-ignore="true"></div>

  <script src="engine.js"></script>
</body>
</html>
"""

with open(os.path.join(video_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

print("Updated build/benchmark_v2/video/index.html with contract tags.")
