"""The site's yearly institution counts with hospitals in their universities. Usage: python 10-31-26/scripts/v11_inst_years.py   (from the IMPACT folder)"""
import os
import sys

os.environ["FIG_DIR"] = "v11"
os.environ["INST_MERGE"] = "institution_merge_v11.csv"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v10_base as B  # noqa: E402
import v7_inst_years as Y  # noqa: E402

Y.F = B.F1
Y.main()
