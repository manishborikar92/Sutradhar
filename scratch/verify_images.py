from PIL import Image
from pathlib import Path

for name in ["sample_01_cosmos", "sample_02_epics"]:
    for g in ["qa_grid.jpg", "qa_grid_safezones.jpg", "final_qa_grid.jpg"]:
        p = Path(f"build/samples/{name}/{g}")
        im = Image.open(p)
        print(f"{p}: size={p.stat().st_size} bytes, dimensions={im.size}, mode={im.mode}")
