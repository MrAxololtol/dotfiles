#!/usr/bin/env python3
"""Isolated wallpaper helper regression checks; no desktop commands are executed."""
from pathlib import Path
import tempfile, shutil, subprocess, os, json, time

REPOSITORY = Path(__file__).resolve().parents[1]
work = Path(tempfile.mkdtemp(prefix='wallpaper-flow-test-'))
bin_dir = work / 'bin'
bin_dir.mkdir()
for name in ('set-wallpaper', 'changer', 'wallpaper-selector'):
    shutil.copy2(REPOSITORY / 'local' / 'bin' / name, bin_dir / name)

common = '''#!/usr/bin/env python3
import os, sys, time, json
from pathlib import Path
with open(os.environ['FLOW_LOG'], 'a') as log:
    log.write(json.dumps({'command': Path(sys.argv[0]).name, 'event':'start', 'args':sys.argv[1:]}) + '\\n')
time.sleep(float(os.environ.get('FLOW_DELAY', '0')))
'''
(bin_dir / 'feh').write_text(common + '''
with open(os.environ['FLOW_LOG'], 'a') as log:
    log.write(json.dumps({'command':'feh', 'event':'end', 'args':sys.argv[1:]}) + '\\n')
sys.exit(int(os.environ.get('FLOW_FEH_STATUS', '0')))
''')
(bin_dir / 'colorChange').write_text(common + '''
state=Path(os.environ['XDG_CACHE_HOME']) / 'colorChange'
state.mkdir(parents=True,exist_ok=True)
(state/'last-wallpaper').write_text(sys.argv[1]+'\\n')
with open(os.environ['FLOW_LOG'], 'a') as log:
    log.write(json.dumps({'command':'colorChange', 'event':'end', 'args':sys.argv[1:]}) + '\\n')
sys.exit(int(os.environ.get('FLOW_COLOR_STATUS','0')))
''')
(bin_dir / 'sxiv').write_text('''#!/usr/bin/env python3
import os,sys
sys.stdout.write(os.environ.get('FLOW_SELECTION',''))
sys.exit(int(os.environ.get('FLOW_SXIV_STATUS','0')))
''')
for path in bin_dir.iterdir():
    path.chmod(0o755)

wall_dir = work/'wall papers'
wall_dir.mkdir()
wall_a = wall_dir/'one blue.png'
wall_b = wall_dir/'two green.JPEG'
wall_a.touch()
wall_b.touch()
log = work / 'calls.jsonl'
env = dict(os.environ, PATH=str(bin_dir)+':'+os.environ['PATH'],
           XDG_CACHE_HOME=str(work/'cache'), WALL_DIR=str(wall_dir), FLOW_LOG=str(log))

checks=[]
def reset():
    log.write_text('')
def events():
    return [json.loads(line) for line in log.read_text().splitlines()]
def run(name,*args,**extra):
    return subprocess.run([str(bin_dir/name),*map(str,args)],env=dict(env,**extra),
                          cwd=work,text=True,capture_output=True,timeout=15)
def passed(name):
    checks.append(name)
    print('PASS:',name)

reset()
r=run('set-wallpaper','wall papers/one blue.png')
assert r.returncode==0,(r.returncode,r.stderr)
assert events()[0]['args']==['--bg-fill','--',str(wall_a)]
assert events()[2]['args']==[str(wall_a)]
passed('relative wallpaper path with spaces resolves correctly; feh precedes palette')

reset()
r=run('set-wallpaper',str(work/'missing.png'))
assert r.returncode!=0 and events()==[]
passed('missing wallpaper fails before either desktop action')

reset()
r=run('set-wallpaper',wall_a,FLOW_FEH_STATUS='9')
assert r.returncode==9 and not any(e['command']=='colorChange' for e in events())
passed('failed wallpaper application never invokes palette update')

reset()
r=run('set-wallpaper',wall_a,FLOW_COLOR_STATUS='8')
assert r.returncode==8
passed('palette failure propagates to caller')

reset()
assert run('set-wallpaper',wall_b).returncode==0
assert run('set-wallpaper','--restore').returncode==0
assert [e['args'] for e in events() if e['command']=='feh' and e['event']=='start']==[['--bg-fill','--',str(wall_b)]]*2
passed('persisted wallpaper restores by exact path including spaces')

for selection,status in (('', '0'),('', '1'),(str(wall_a),'1')):
    reset()
    r=run('wallpaper-selector',FLOW_SELECTION=selection,FLOW_SXIV_STATUS=status)
    assert r.returncode==0 and events()==[]
passed('empty picker output and cancelled picker leave wallpaper and palette untouched')

reset()
r=run('wallpaper-selector',FLOW_SELECTION=str(wall_a)+'\n'+str(wall_b)+'\n')
assert r.returncode==0 and events()[0]['args']==['--bg-fill','--',str(wall_a)]
passed('picker applies the first selected image and refreshes its palette')

reset()
r=run('changer')
assert r.returncode==0 and events()[0]['args'][2] in (str(wall_a),str(wall_b))
passed('random changer includes mixed case supported extensions and refreshes palette')

empty=work/'empty';empty.mkdir()
reset()
r=run('changer',WALL_DIR=str(empty))
assert r.returncode!=0 and events()==[]
passed('empty wallpaper directory has no desktop effects')

reset()
p1=subprocess.Popen([str(bin_dir/'set-wallpaper'),str(wall_a)],env=dict(env,FLOW_DELAY='0.10'))
time.sleep(0.02)
p2=subprocess.Popen([str(bin_dir/'set-wallpaper'),str(wall_b)],env=dict(env,FLOW_DELAY='0.10'))
assert p1.wait(timeout=15)==0 and p2.wait(timeout=15)==0
assert [(e['command'],e['event']) for e in events()]== [('feh','start'),('feh','end'),('colorChange','start'),('colorChange','end')]*2
assert events()[0]['args'][2]==events()[2]['args'][0]
assert events()[4]['args'][2]==events()[6]['args'][0]
passed('concurrent selections serialize wallpaper and corresponding palette as one operation')

sxhkd=(REPOSITORY / 'config' / 'sxhkd' / 'sxhkdrc').read_text()
for chord,name in [('super + alt + w','changer'),('ctrl + alt + w','changer'),('super + alt + e','wallpaper-selector'),('ctrl + alt + e','wallpaper-selector')]:
    assert chord+'\n    "$HOME/.local/bin/'+name+'"' in sxhkd
bspwm=(REPOSITORY / 'config' / 'bspwm' / 'bspwmrc').read_text()
assert '"$HOME/.local/bin/set-wallpaper" --restore &' in bspwm
assert 'export PATH="$HOME/.local/bin:$PATH"' in bspwm
passed('both wallpaper hotkey families and session restore target installed local helpers')
print(f'{len(checks)} checks passed; isolated logs: {work}')
