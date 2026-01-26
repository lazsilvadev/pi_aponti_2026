import re

p = r"c:/Users/L/Music/Nova pasta/Mercadinho/caixa/view.py"
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()
stack = []
for i, line in enumerate(lines[:3600]):
    m_try = re.match(r"^(\s*)try:\s*(#.*)?$", line)
    m_exc = re.match(r"^(\s*)(except\b|finally\b).*$", line)
    if m_try:
        indent = len(m_try.group(1))
        stack.append((i + 1, indent))
    if m_exc:
        indent = len(m_exc.group(1))
        # pop nearest try with same indent
        for j in range(len(stack) - 1, -1, -1):
            if stack[j][1] == indent:
                stack.pop(j)
                break

print("Unmatched try blocks up to line 3600:")
for ln, ind in stack[-50:]:
    print("  try at", ln, "indent", ind)
print("Total unmatched:", len(stack))
