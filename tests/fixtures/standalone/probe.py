"""Synthetic candidate: exercise declared files and actual identity, without vendor login."""
import json
import os
import pwd
import subprocess
import sys
import time
from pathlib import Path

request=json.loads(Path('/in/request.json').read_text())
workspace=Path(request['workspace_path'])
output=Path(request['proposal_path'])
prompt=Path(request['prompt_path']).read_text()
assert 'Implement every card' in prompt
assert (workspace/'initializer.txt').read_text()=='prepared'
account=pwd.getpwuid(os.getuid())
sudo=subprocess.run(['sudo','-n','id','-u'],capture_output=True,text=True)
observation={'uid':os.getuid(),'gid':os.getgid(),'account':account.pw_name,'home':os.environ.get('HOME'),'sudo':sudo.returncode==0 and sudo.stdout.strip()=='0','variant':os.environ.get('BENCH_VARIANT'),'initializer':True,'prompt':bool(prompt)}
(workspace/'fixture-observation.json').write_text(json.dumps(observation))
behavior=os.environ.get('BENCH_BEHAVIOR','valid')
if behavior=='timeout':time.sleep(120)
proposal={'schema_version':1,'mode':'run','fields':{'pr-title':'Exercise standalone candidate','pr-description':'Validate declared inputs, identity and outputs.','commit-message':'Exercise standalone candidate\n\nUse the selected definition without runtime packages.','decisions':[{'what':'Use declared files','why':'Preserve the benchmark boundary.'}]}}
if behavior=='invalid':proposal={'unexpected':True}
output.write_text(json.dumps(proposal))
print('standalone fixture completed',flush=True)
sys.exit(7 if behavior=='failed' else 0)
