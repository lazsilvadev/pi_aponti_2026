import os

for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith(".db") or f.endswith(".sqlite"):
            print(os.path.abspath(os.path.join(root, f)))
