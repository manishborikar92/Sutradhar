import re

styles_path = "build/benchmark_v2_1/video_en/styles.css"
with open(styles_path, "r", encoding="utf-8") as f:
    css = f.read()

rig_css = """
/* NATIVE CSS TRANSFORM ROTATIONS VIA CSS CUSTOM PROPERTIES (Locked to 0px 0px rivets) */
#upper_arm_rear_left_rot {
  transform: rotate(var(--rot-rear-arm-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#forearm_rear_left_rot {
  transform: rotate(var(--rot-rear-fore-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#weapon_chandrahas_rot {
  transform: rotate(var(--rot-chandrahas, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#upper_arm_rear_right_rot {
  transform: rotate(var(--rot-rear-arm-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#forearm_rear_right_rot {
  transform: rotate(var(--rot-rear-fore-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#weapon_gada_rot {
  transform: rotate(var(--rot-gada, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#upper_arm_front_left_rot {
  transform: rotate(var(--rot-front-arm-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#forearm_front_left_rot {
  transform: rotate(var(--rot-front-fore-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#upper_arm_front_right_rot {
  transform: rotate(var(--rot-front-arm-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#forearm_front_right_rot {
  transform: rotate(var(--rot-front-fore-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}

#thigh_left_rot {
  transform: rotate(var(--rot-thigh-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#shin_left_rot {
  transform: rotate(var(--rot-shin-left, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#thigh_right_rot {
  transform: rotate(var(--rot-thigh-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
#shin_right_rot {
  transform: rotate(var(--rot-shin-right, 0deg)) !important;
  transform-origin: 0px 0px !important;
}
"""

with open(styles_path, "w", encoding="utf-8") as f:
    f.write(css + "\n" + rig_css)

print("Appended native CSS transform custom properties to video_en/styles.css")
