"""Run live_bench.py and also print the server's verify counter."""
import json, os, runpy
_ls = json.loads
def _loads(*a, **k):
    o = _ls(*a, **k)
    if isinstance(o, dict) and "verify" in o:
        print("VERIFY_STATS", o["verify"], flush=True)
    return o
json.loads = _loads
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_bench.py"), run_name="__main__")
