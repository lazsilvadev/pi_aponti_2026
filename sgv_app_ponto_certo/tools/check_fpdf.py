import importlib

try:
    m = importlib.import_module("fpdf")
    print("module", m)
    print("file", getattr(m, "__file__", None))
    print("FPDF?", hasattr(m, "FPDF"))
    print("attrs:", [a for a in dir(m) if not a.startswith("_")])
except Exception as e:
    print("IMPORT ERROR", e)
