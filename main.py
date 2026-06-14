"""
svg-decompose-to-drawio: Convert SVG files into editable draw.io diagrams.

Each SVG element becomes an individual, selectable cell - not a single embedded image.

Usage:
    python main.py <svg_file_or_folder>
    python main.py                          # prompts for path
"""

import sys
from os import listdir, path

from svg_to_drawio import convert_file


def run(input_path):
    if path.isdir(input_path):
        svgs = [f for f in listdir(input_path) if f.lower().endswith('.svg')]
        if not svgs:
            print('No SVG files found in folder.')
            return
        for fname in sorted(svgs):
            fp = path.join(input_path, fname)
            out = convert_file(fp)
            print(f'Converted: {fname}  ->  {path.basename(out)}')
    elif path.isfile(input_path) and input_path.lower().endswith('.svg'):
        out = convert_file(input_path)
        print(f'Converted: {path.basename(input_path)}  ->  {path.basename(out)}')
    else:
        print(f'Error: "{input_path}" is not a valid SVG file or directory.')
        sys.exit(1)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else input('Enter SVG file or folder path: ')
    run(target)
