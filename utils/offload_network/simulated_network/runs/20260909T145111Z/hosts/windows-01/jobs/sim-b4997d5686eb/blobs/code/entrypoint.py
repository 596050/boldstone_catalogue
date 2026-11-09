import csv,json,pathlib,sys
rows=list(csv.DictReader(pathlib.Path('blobs/data/prices.csv').open()))
pathlib.Path('result.json').write_text(json.dumps({'rows':rows,'arg':sys.argv[1]}))
pathlib.Path('artifacts').mkdir()
pathlib.Path('artifacts/worker.txt').write_text('isolated')
