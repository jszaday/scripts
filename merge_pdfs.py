#!/usr/bin/env python3
# merge_pdfs.py — concatenate multiple PDF files into one.
# Usage: ./merge_pdfs.py output.pdf input1.pdf input2.pdf [...]

import argparse
from PyPDF2 import PdfMerger


def main():
    parser = argparse.ArgumentParser(
        description="Concatenate multiple PDF files into a single output PDF."
    )
    parser.add_argument("output", help="Path for the merged output PDF")
    parser.add_argument("inputs", nargs="+", help="Input PDFs in order")
    args = parser.parse_args()

    merger = PdfMerger()
    for pdf in args.inputs:
        print(f"Adding: {pdf}")
        merger.append(pdf)
    merger.write(args.output)
    merger.close()
    print(f"Merged into: {args.output}")


if __name__ == "__main__":
    main()
