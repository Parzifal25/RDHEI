"""Repeat the fixed gate into a new directory, preserving all previous evidence."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys
from pathlib import Path
import run_gate

if len(sys.argv)!=2:
    raise ValueError('usage: reproduce.py NEW_OUTPUT_DIRECTORY')
run_gate.D=Path(sys.argv[1]).resolve()
run_gate.main()
