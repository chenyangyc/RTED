from pathlib import Path
import os

current_script_dir = Path(__file__).parent
for path in current_script_dir.iterdir():
    if path.suffix == '.txt':
        path.rename(str(path).replace('typebugs_', ''))