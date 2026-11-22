"""Keep original short films, and split longer originals into complete ordered clips."""
import json,math,subprocess,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
rows=json.loads((OUT/'source-video-receipts.json').read_text());clips=[]
folder=OUT/'google-delivery-video';folder.mkdir(exist_ok=True)
for row in rows:
 if row['status']!='SOURCE_VIDEO_VERIFIED':continue
 source=Path(row['media_path']);assert digest(source.read_bytes())==row['sha256']
 duration=row['duration'];parts=math.ceil(duration/29.5)
 for part in range(parts):
  start=duration*part/parts;end=duration*(part+1)/parts
  if parts==1 and source.stat().st_size<=5_000_000:delivery=source;command=None
  else:
   delivery=folder/(row['shortcode']+'-part-'+str(part+1)+'-of-'+str(parts)+'.mp4')
   command=['/opt/homebrew/bin/ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-ss',str(start),'-i',str(source),'-t',str(end-start),'-map','0:v:0','-map','0:a?','-c:v','libx264','-threads','2','-preset','veryfast','-crf','22','-maxrate','1000k','-bufsize','2000k','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart',str(delivery)]
   if not delivery.exists():subprocess.run(command,check=True)
  result=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_format','-show_streams','-of','json',str(delivery)],capture_output=True,text=True,check=True);metadata=json.loads(result.stdout)
  assert float(metadata['format']['duration'])<=30 and delivery.stat().st_size<=5_000_000
  video=next(s for s in metadata['streams'] if s['codec_type']=='video');assert min(video['width'],video['height'])>=720
  clips.append({**row,'original_media_path':str(source),'original_sha256':row['sha256'],'delivery_media_path':str(delivery.resolve()),'delivery_sha256':digest(delivery.read_bytes()),'delivery_bytes':delivery.stat().st_size,'delivery_duration':float(metadata['format']['duration']),'part_number':part+1,'part_count':parts,'source_start_seconds':start,'source_end_seconds':end,'conversion_command':command,'delivery_metadata':metadata})
  print(json.dumps({'shortcode':row['shortcode'],'part':part+1,'parts':parts,'bytes':delivery.stat().st_size,'duration':float(metadata['format']['duration'])}),flush=True)
atomic_json(OUT/'google-video-delivery-plan.json',{'utc':utc(),'status':'PREPARED_NOT_PUBLISHED','clips':clips,'original_films':sum(r['status']=='SOURCE_VIDEO_VERIFIED' for r in rows),'all_original_footage_retained_in_order':True,'reference':'https://support.google.com/business/answer/6103862?hl=en'})
