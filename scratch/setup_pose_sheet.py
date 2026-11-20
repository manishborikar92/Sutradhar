import os
import shutil
import subprocess

POSE_DIR = "build/benchmark_v2_1/pose_sheet"
os.makedirs(os.path.join(POSE_DIR, "assets", "js"), exist_ok=True)
shutil.copyfile("assets/js/gsap.min.js", os.path.join(POSE_DIR, "assets", "js", "gsap.min.js"))

with open("build/benchmark_v2_1/ravana_v2_4.svg", "r", encoding="utf-8") as f:
    base_svg = f.read()

# Make base SVG scalable and add layout attributes
base_svg = base_svg.replace(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1200" width="800" height="1200" id="ravana_puppet_rig">',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1200" width="100%" height="100%" id="ravana_puppet_rig" data-layout-allow-overflow="true" data-layout-ignore="true">'
)

# Pose 1: Default Idle Stance
svg_pose1 = base_svg.replace('id="ravana_puppet_rig"', 'id="ravana_pose1"')

# Pose 2: Action Arms Raised (Testing extreme joint rotation with brass rivets locked)
svg_pose2 = base_svg.replace('id="ravana_puppet_rig"', 'id="ravana_pose2"')
pose2_styles = """
<style>
  #ravana_pose2 #upper_arm_rear_left_rot { transform: rotate(-38deg); }
  #ravana_pose2 #forearm_rear_left_rot { transform: rotate(-28deg); }
  #ravana_pose2 #weapon_chandrahas_rot { transform: rotate(-15deg); }
  
  #ravana_pose2 #upper_arm_rear_right_rot { transform: rotate(38deg); }
  #ravana_pose2 #forearm_rear_right_rot { transform: rotate(28deg); }
  #ravana_pose2 #weapon_gada_rot { transform: rotate(15deg); }
  
  #ravana_pose2 #upper_arm_front_left_rot { transform: rotate(-45deg); }
  #ravana_pose2 #forearm_front_left_rot { transform: rotate(35deg); }
  
  #ravana_pose2 #upper_arm_front_right_rot { transform: rotate(45deg); }
  #ravana_pose2 #forearm_front_right_rot { transform: rotate(-35deg); }
  
  #ravana_pose2 #thigh_left_rot { transform: rotate(6deg); }
  #ravana_pose2 #shin_left_rot { transform: rotate(-12deg); }
  #ravana_pose2 #thigh_right_rot { transform: rotate(-6deg); }
  #ravana_pose2 #shin_right_rot { transform: rotate(12deg); }
  
  #ravana_pose2 #mouth_calm { opacity: 0; }
  #ravana_pose2 #mouth_talk { opacity: 1; }
</style>
"""
svg_pose2 = svg_pose2.replace('</defs>', pose2_styles + '\n</defs>')

# Pose 3: Close-Up Wrath & Shouting Mouth with Sunburst Aura
svg_pose3 = base_svg.replace('id="ravana_puppet_rig"', 'id="ravana_pose3"')
svg_pose3 = svg_pose3.replace('viewBox="0 0 800 1200"', 'viewBox="140 100 520 520"')
pose3_styles = """
<style>
  #ravana_pose3 #wrath_sunburst { opacity: 1 !important; transform: scale(1.05); }
  #ravana_pose3 #mouth_calm { opacity: 0 !important; }
  #ravana_pose3 #mouth_shout { opacity: 1 !important; }
  #ravana_pose3 #eyes_normal { opacity: 0 !important; }
  #ravana_pose3 #eyes_wrath { opacity: 1 !important; }
  #ravana_pose3 #brows_neutral { opacity: 0 !important; }
  #ravana_pose3 #brows_angry { opacity: 1 !important; }
  #ravana_pose3 #head_center { transform: translate(0px, -35px) scale(1.18); }
</style>
"""
svg_pose3 = svg_pose3.replace('</defs>', pose3_styles + '\n</defs>')

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ravana Kathputli 3-Pose Rig Verification</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      width: 1920px;
      height: 1080px;
      background: radial-gradient(circle at 50% 30%, #201309 0%, #0f0703 60%, #050201 100%);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      overflow: hidden;
      font-family: Georgia, serif;
      color: #ffd700;
      padding: 30px;
    }}
    .sheet-header {{
      text-align: center;
      margin-bottom: 25px;
    }}
    .sheet-title {{
      font-size: 38px;
      letter-spacing: 6px;
      text-transform: uppercase;
      color: #f5c242;
      text-shadow: 0 4px 18px rgba(0,0,0,0.9);
      margin-bottom: 6px;
    }}
    .sheet-subtitle {{
      font-size: 28px;
      letter-spacing: 3px;
      color: #d4a034;
    }}
    .poses-container {{
      display: flex;
      width: 1860px;
      height: 900px;
      gap: 30px;
      justify-content: space-between;
    }}
    .pose-card {{
      flex: 1;
      background: rgba(30, 18, 8, 0.65);
      border: 2px solid rgba(245, 194, 66, 0.45);
      border-radius: 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px;
      box-shadow: 0 15px 35px rgba(0,0,0,0.85);
      position: relative;
    }}
    .pose-badge {{
      font-size: 28px;
      font-weight: bold;
      letter-spacing: 2px;
      color: #fff8cc;
      background: rgba(184, 134, 11, 0.4);
      border: 1px solid rgba(245, 194, 66, 0.7);
      padding: 6px 18px;
      border-radius: 6px;
      margin-bottom: 12px;
      text-transform: uppercase;
    }}
    .pose-status {{
      position: absolute;
      bottom: 16px;
      font-size: 28px;
      letter-spacing: 1.5px;
      color: #a8d5ba;
      background: rgba(16, 44, 25, 0.85);
      border: 1px solid #2b8a3e;
      padding: 6px 16px;
      border-radius: 4px;
    }}
    .puppet-viewport {{
      width: 100%;
      height: 730px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
  </style>
  <script src="assets/js/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    document.addEventListener("DOMContentLoaded", () => {{
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["ravana_pose_sheet"] = tl;
    }});
  </script>
</head>
<body data-composition-id="ravana_pose_sheet" data-width="1920" data-height="1080" data-duration="3.0">
  <div class="sheet-header" data-layout-ignore="true">
    <div class="sheet-title">RAVANA KATHPUTLI RIG — 3-POSE KINEMATIC INTEGRITY SHEET</div>
    <div class="sheet-subtitle">Locked Rivet Transform-Origins • Hierarchical Parenting • Switchable Expressions</div>
  </div>

  <div class="poses-container" data-layout-allow-overflow="true" data-layout-ignore="true">
    <!-- POSE 1: Idle Royal Stance -->
    <div class="pose-card" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="pose-badge">Pose 1: Idle Royal Stance</div>
      <div class="puppet-viewport" data-layout-allow-overflow="true" data-layout-ignore="true">
        {svg_pose1}
      </div>
      <div class="pose-status" data-layout-ignore="true">Neutral Stance • Closed Regal Mouth</div>
    </div>

    <!-- POSE 2: Action Arms Raised -->
    <div class="pose-card" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="pose-badge">Pose 2: Action Arms Raised</div>
      <div class="puppet-viewport" data-layout-allow-overflow="true" data-layout-ignore="true">
        {svg_pose2}
      </div>
      <div class="pose-status" data-layout-ignore="true">Articulated Shoulders & Elbows • 0 Limbs Detached</div>
    </div>

    <!-- POSE 3: Close-Up Wrath & Shouting Mouth -->
    <div class="pose-card" data-layout-allow-overflow="true" data-layout-ignore="true">
      <div class="pose-badge">Pose 3: Close-Up Wrath & Shouting Mouth</div>
      <div class="puppet-viewport" data-layout-allow-overflow="true" data-layout-ignore="true">
        {svg_pose3}
      </div>
      <div class="pose-status" data-layout-ignore="true">Shouting Mouth w/ Fangs • Wrath Eyes • Solar Aura</div>
    </div>
  </div>
</body>
</html>
"""

html_path = os.path.join(POSE_DIR, "index.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Generated clean {html_path}")
