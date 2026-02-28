"""Copy raw SEC JSON files into the project's `raw_data/` folder.

This is a one-off local helper and is not used by the Flask app at runtime.
"""

from __future__ import annotations

import os
import shutil


def main() -> None:
    src_dir = "/Users/stefan/Downloads/companyfacts"
    dst_dir = "raw_data/companyfacts"

    os.makedirs(dst_dir, exist_ok=True)

    for filename in os.listdir(src_dir):
        src_file = os.path.join(src_dir, filename)
        dst_file = os.path.join(dst_dir, filename)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)


if __name__ == "__main__":
    main()
