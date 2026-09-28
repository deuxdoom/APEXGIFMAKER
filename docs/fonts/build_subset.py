"""Rebuild the local webfont after editing page text.

Requires fonttools and brotli. Run from any directory:
    python docs/fonts/build_subset.py --source assets/fonts/PretendardVariable.ttf
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fontTools import subset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    text = "".join((root / name).read_text(encoding="utf-8")
                   for name in ("index.html", "site.css", "site.js"))
    options = subset.Options()
    options.flavor = "woff2"
    font = subset.load_font(str(args.source), options)
    # Modified fonts must not retain the OFL Reserved Font Name.
    for record in font["name"].names:
        if record.nameID in (1, 3, 4, 6, 16, 18, 21, 25):
            name = record.toUnicode().replace("Pretendard", "ApexSiteSans")
            record.string = name.encode(record.getEncoding())
    builder = subset.Subsetter(options=options)
    builder.populate(text=text + "".join(chr(i) for i in range(32, 127)))
    builder.subset(font)
    target = root / "fonts" / "apex-site-sans.woff2"
    subset.save_font(font, str(target), options)
    print(f"Saved {target.name}: {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
