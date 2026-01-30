import sys

p = "produtos/relatorio_produtos.py"
s = open(p, encoding="utf-8").read()
ln = 1
col = 0
stack = []
for ch in s:
    if ch == "\n":
        ln += 1
        col = 0
        continue
    col += 1
    if ch == "[":
        stack.append((ch, ln, col))
    elif ch == "]":
        if stack:
            stack.pop()
        else:
            print("Extra closing ] at", ln, col)
if stack:
    print("Unclosed [ positions (last 40):")
    for item in stack[-40:]:
        print(item)
else:
    print("All brackets matched")
