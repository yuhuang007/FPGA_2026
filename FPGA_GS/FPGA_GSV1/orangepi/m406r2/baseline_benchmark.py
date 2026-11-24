"""Temporary full ORIGINAL m406 benchmark. Only runtime evidence path differs.
No original source, default entry, port8080, or business UDP is changed.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'m406'))
p=ROOT/'m406/demo.py'
s=p.read_text().replace("ROOT/'m406/evidence/runtime'","ROOT/'m406r2/evidence/baseline_runtime'")
exec(compile(s,str(p),'exec'),dict(__name__='__main__',__file__=str(p)))
