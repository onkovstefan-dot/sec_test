import os
import shutil

src_dir = '/Users/stefan/Downloads/companyfacts'
dst_dir = 'raw_data/companyfacts'

if not os.path.exists(dst_dir):
    os.makedirs(dst_dir)

for filename in os.listdir(src_dir):
    src_file = os.path.join(src_dir, filename)
    dst_file = os.path.join(dst_dir, filename)
    if os.path.isfile(src_file):
        shutil.copy2(src_file, dst_file)