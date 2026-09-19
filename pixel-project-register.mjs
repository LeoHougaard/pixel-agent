import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
import {rpc} from './pixel-t3-watch.mjs';
const exec=promisify(execFile);
const [entry,workspaceRoot,title]=process.argv.slice(2);
let session;
try {
  session=JSON.parse((await exec(process.execPath,[entry,'auth','session','issue','--ttl','5m','--label','Pixel project picker','--json'],{timeout:60000})).stdout);
  const response=await fetch('http://127.0.0.1:3773/api/orchestration/shell',{headers:{Authorization:`Bearer ${session.token}`},signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw Error('Could not read T3 projects');
  const shell=await response.json();
  let project=shell.projects.find(p=>p.workspaceRoot===workspaceRoot && !p.deletedAt);
  if(!project){
    project={id:randomUUID(),title};
    const model=shell.projects.find(p=>p.defaultModelSelection?.instanceId==='opencode')?.defaultModelSelection
      ?? {instanceId:'opencode',model:'opencode/muse-spark-1.3-contributor-free'};
    await rpc(session.token,'orchestration.dispatchCommand',{type:'project.create',commandId:randomUUID(),projectId:project.id,
      workspaceRoot,title,defaultModelSelection:model,createdAt:new Date().toISOString()});
  }
  console.log(JSON.stringify({project_id:project.id,project_title:project.title}));
}catch{console.log(JSON.stringify({error:'Could not register the repository with T3. Reconnect and try again.'}));process.exitCode=1;}
finally{if(session)await exec(process.execPath,[entry,'auth','session','revoke',session.sessionId],{timeout:15000}).catch(()=>{});}
