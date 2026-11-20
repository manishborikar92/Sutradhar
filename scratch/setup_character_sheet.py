import os
import shutil

sheet_dir = "build/benchmark_v2/character_sheet"
os.makedirs(os.path.join(sheet_dir, "assets", "js"), exist_ok=True)
shutil.copyfile("assets/js/gsap.min.js", os.path.join(sheet_dir, "assets", "js", "gsap.min.js"))

with open("build/benchmark_v2/ravana_v2.svg", "r", encoding="utf-8") as f:
    svg_content = f.read()

# Make sure the SVG scales nicely in the container
svg_inline = svg_content.replace('width="800" height="1200"', 'width="100%" height="100%"')

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ravana Kathputli Character Sheet</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      width: 1080px;
      height: 1920px;
      background: radial-gradient(circle at 50% 40%, #24160d 0%, #120904 70%, #080402 100%);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      font-family: 'Playfair Display', serif;
      color: #ffd700;
    }}
    .sheet-header {{
      text-align: center;
      margin-top: 40px;
      margin-bottom: 20px;
    }}
    .sheet-title {{
      font-size: 44px;
      letter-spacing: 5px;
      text-transform: uppercase;
      margin-bottom: 12px;
      color: #f5c242;
      text-shadow: 0 4px 16px rgba(0,0,0,0.9);
    }}
    .sheet-subtitle {{
      font-size: 28px;
      letter-spacing: 2px;
      color: #d4a034;
    }}
    .puppet-frame {{
      width: 820px;
      height: 1230px;
      display: flex;
      align-items: center;
      justify-content: center;
      filter: drop-shadow(0 25px 50px rgba(0,0,0,0.95));
      margin: 10px 0;
    }}
    .callout-grid {{
      margin-top: 30px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      width: 820px;
    }}
    .callout-row {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
    }}
    .callout-item {{
      flex: 1;
      background: rgba(245, 194, 66, 0.08);
      border: 1.5px solid rgba(245, 194, 66, 0.4);
      padding: 14px 20px;
      border-radius: 8px;
      font-size: 28px;
      color: #f0dfc0;
      text-align: center;
    }}
  </style>
  <script src="assets/js/gsap.min.js"></script>
</head>
<body data-composition-id="character_sheet" data-width="1080" data-height="1920" data-duration="3.0">
  <div class="sheet-header">
    <div class="sheet-title">RAVANA — 2D KATHPUTLI RIG</div>
    <div class="sheet-subtitle">Lanka Sovereign • 5-Head Articulated Puppet</div>
  </div>
  
  <div class="puppet-frame" id="puppet_container">
    {svg_inline}
  </div>

  <div class="callout-grid">
    <div class="callout-row">
      <div class="callout-item">Articulated Brass Rivet Pins</div>
      <div class="callout-item">5 Expressive Tiered Mukuts</div>
    </div>
    <div class="callout-row">
      <div class="callout-item">Shaded Olive Skin &amp; Sacred Janeu</div>
      <div class="callout-item">Gold Zari Pleated Crimson Dhoti</div>
    </div>
  </div>

  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true }});
    // Subtle breathing posture
    tl.to("#puppet_container", {{ scale: 1.02, y: -10, duration: 1.5, ease: "sine.inOut" }})
      .to("#puppet_container", {{ scale: 1.0, y: 0, duration: 1.5, ease: "sine.inOut" }});
    window.__timelines["character_sheet"] = tl;
  </script>
</body>
</html>
"""

with open(os.path.join(sheet_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Created {os.path.join(sheet_dir, 'index.html')} with inlined SVG and local GSAP.")
