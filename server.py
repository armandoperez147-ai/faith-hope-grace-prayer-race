from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, secrets, time, threading, os, urllib.parse
ROOT=Path(__file__).resolve().parent
QUESTIONS=json.loads((ROOT/'questions.json').read_text())
ROOMS={}
LOCK=threading.RLock()
NAMES=['Faith','Hope','Grace']
def state(r):
 q=QUESTIONS[r['index']]
 return dict(code=r['code'],phase=r['phase'],index=r['index'],startedAt=r['startedAt'],teams=[dict(name=n,connected=bool(r['teams'][n]['token']),score=r['teams'][n]['score'],correct=r['teams'][n]['correct'],answered=r['teams'][n]['answer'] is not None,lastPoints=r['teams'][n]['lastPoints']) for n in NAMES],question=dict(text=q[0],options=q[1]) if r['phase'] in ('question','reveal') else None,reveal=dict(correct=q[2],reference=q[3],explanation=q[4]) if r['phase']=='reveal' else None)
def handle(action,d):
 c=str(d.get('code','')).upper()
 if action=='create':
  c=secrets.token_hex(3).upper()
  while c in ROOMS:c=secrets.token_hex(3).upper()
  token=secrets.token_urlsafe(24)
  ROOMS[c]=dict(code=c,hostToken=token,phase='lobby',index=0,startedAt=0,teams={n:dict(token=None,score=0,correct=0,answer=None,at=None,lastPoints=0) for n in NAMES})
  return dict(code=c,token=token)
 r=ROOMS.get(c)
 if not r:return dict(error='Room not found')
 team=d.get('team');token=d.get('token')
 if action=='join':
  if team not in NAMES:return dict(error='Choose a team')
  t=r['teams'][team]
  if t['token'] and t['token']!=token:return dict(error='Team already taken')
  if not t['token']:t['token']=secrets.token_urlsafe(24)
  return dict(code=c,team=team,token=t['token'])
 host=secrets.compare_digest(str(token or ''),r['hostToken'])
 player=team in NAMES and bool(token) and secrets.compare_digest(str(token),str(r['teams'][team]['token'] or ''))
 if action=='state':
  if not(host or player):return dict(error='Not authorized')
  return state(r)
 if action in ('start','reveal','next','restart') and not host:return dict(error='Host only')
 if action=='answer' and not player:return dict(error='Team only')
 if action=='start':
  if r['phase']!='lobby':return dict(error='Cannot start')
  r['phase']='question';r['startedAt']=time.time()*1000
 elif action=='answer':
  t=r['teams'][team];choice=d.get('choice')
  if r['phase']!='question' or t['answer'] is not None or type(choice)!=int or choice not in range(4):return dict(error='Answer not accepted')
  t['answer']=choice;t['at']=time.time()*1000
 elif action=='reveal':
  if r['phase']!='question':return dict(error='Cannot reveal')
  for n in NAMES:
   t=r['teams'][n];right=t['answer']==QUESTIONS[r['index']][2]
   elapsed=max(0,(t['at'] or float('inf'))-r['startedAt'])
   bonus=max(0,round(300*(1-elapsed/20000))) if right else 0
   t['lastPoints']=1000+bonus if right else 0;t['score']+=t['lastPoints']
   if right:t['correct']+=1
  r['phase']='reveal'
 elif action=='next':
  if r['phase']!='reveal':return dict(error='Cannot advance')
  if r['index']==19:r['phase']='finished'
  else:
   r['index']+=1;r['phase']='question';r['startedAt']=time.time()*1000
   for n in NAMES:r['teams'][n].update(answer=None,at=None,lastPoints=0)
 elif action=='restart':
  r['index']=0;r['phase']='lobby'
  for n in NAMES:r['teams'][n].update(score=0,correct=0,answer=None,at=None,lastPoints=0)
 else:return dict(error='Unknown action')
 return dict(ok=True)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  if not self.path.startswith('/api/'):return self.send_error(404)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>4096:return self.send_error(413)
   data=json.loads(self.rfile.read(length))
   with LOCK:result=handle(self.path.split('/')[-1],data)
   self.send_json(result)
  except Exception:self.send_json(dict(error='Invalid request'),400)
 def send_json(self,obj,status=200):
  b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/health':return self.send_json(dict(ok=True))
  if urllib.parse.urlparse(self.path).path not in ('/','/index.html'):return self.send_error(404)
  b=(ROOT/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=='__main__':
 port=int(os.environ.get('PORT',10000));print('Prayer Race on port',port,flush=True);ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
