import json,pathlib,sys
from render_visual_family import run
P=pathlib.Path(__file__).resolve().parent
queue=json.loads((P/'remaining-family-render-queue.json').read_text())[sys.argv[1]]
for family in queue:run(family)
