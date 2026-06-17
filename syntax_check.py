import ast
with open(r"C:\Julabo Control\julabo_gui.py", encoding="utf-8") as f:
    src = f.read()
try:
    ast.parse(src)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
