from .converter import Converter


def convert_file(svg_path, out_path=None):
    return Converter().convert_file(svg_path, out_path)
