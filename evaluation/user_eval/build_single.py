"""Build one self-contained HTML file from form/index.html: every screenshot is embedded
once as a data URI, so the file can be sent on its own (WhatsApp, email, Drive)."""
import base64, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "form", "index.html"), encoding="utf-8").read()
names = sorted(set(re.findall(r'"img/([0-9a-z-]+)\.webp"', src)))
imgs = {}
for n in names:
    with open(os.path.join(HERE, "form", "img", n + ".webp"), "rb") as fh:
        imgs[n] = "data:image/webp;base64," + base64.b64encode(fh.read()).decode("ascii")
body = re.sub(r'"img/([0-9a-z-]+)\.webp"', r'IMG["\1"]', src)
table = "const IMG = {\n" + ",\n".join(f'  "{n}": "{u}"' for n, u in imgs.items()) + "\n};\n"
body = body.replace("<script>\n(() => {", "<script>\n" + table + "(() => {", 1)
head, rest = body.split("</style>", 1)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       + head.replace("<style>", "<style>\n[hidden] { display: none !important; }\nimg { max-width: 100%; }", 1)
       + "</style>\n</head>\n<body>\n" + rest.strip() + "\n</body>\n</html>\n")
out = os.path.join(HERE, "BrandPulse_Evaluation.html")
open(out, "w", encoding="utf-8").write(doc)
print(f"{out}: {os.path.getsize(out) / 1024 / 1024:.2f} MB, {len(imgs)} images embedded")
