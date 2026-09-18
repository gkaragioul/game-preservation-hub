// Deterministic guard, not a proof that arbitrary code is safe to publish.
import {readFileSync, readdirSync, lstatSync} from 'node:fs';
import {resolve, join, relative, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';

const here = dirname(fileURLToPath(import.meta.url));
const LIMIT = 64 * 1024 * 1024;
const findings = new Set();
let inspected = 0;
const blockedPath = /(^|\/)(?:\.git(?:\/|$)|\.env(?!\.(?:example|sample|template)$)(?:\.|$)|\.porting(?:\/|$)|\.notion(?:\/|$)|node_modules(?:\/|$)|\.venv(?:\/|$)|(?:id_rsa|id_ed25519)(?:$|\.)|(?:extracted|private-research|internal-evidence)(?:\/|$))/i;
const artifact = /\.(?:zip|7z|rar|tar|gz|bz2|xz|exe|dll|pdb|dmp|sqlite|db|wasm|(?:js|css)\.map)$/i;
const rules = [
 ['private-link', /https?:\/\/(?:[a-z0-9-]+\.)?notion\.(?:so|site|com)\//i],
 ['private-core', /RLabs(?:System|Monitor)|intelligence[_]closeout[_]guard|lane[_]intelligence[_]registry|PPC[_]CALL[_]INDIRECT[_]FUNC/],
 ['credential', /(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|ntn_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)/],
 ['source-map', /"sourcesContent"\s*:/],
];
let exceptions = {};
function block(path, kind) { findings.add(`${kind}: ${JSON.stringify(path)}`); }
function scan(path, data, mode = '100644') {
 inspected++;
 if (!/^100(?:644|755)$/.test(mode)) { block(path, 'unsupported-entry'); return; }
 const allowed = exceptions[path];
 const digest = createHash('sha256').update(data).digest('hex');
 const exemptions = allowed?.sha256 === digest && typeof allowed.reason === 'string' ? allowed.rules : [];
 if (blockedPath.test(path) && !exemptions?.includes('private-path')) block(path, 'private-path');
 if (artifact.test(path) && !exemptions?.includes('artifact')) block(path, 'artifact-needs-review');
 const texts = [data.toString('utf8'), new TextDecoder('utf-16le').decode(data), new TextDecoder('utf-16be').decode(data)];
 for (const [kind, regex] of rules) {
   if (!exemptions?.includes(kind) && texts.some(text => regex.test(text))) block(path, kind);
 }
}
async function git(repo, args, options = {}) {
 return await new Promise((accept,reject)=>{
   const child=spawn('git',['-C',repo,...args],{windowsHide:true});
   const chunks=[];let size=0;
   child.on('error',reject);
   child.stdout.on('data',chunk=>{size+=chunk.length;if(size>128*1024*1024){child.kill();reject(new Error('Git output limit'));}else chunks.push(chunk);});
   child.stderr.resume();
   child.stdin.on('error',reject);
   child.on('close',code=>code===0?accept(Buffer.concat(chunks)):reject(new Error('Git inspection failed')));
   child.stdin.end(options.input);
 });
}
async function hashRef(repo, ref) {
 if (ref.startsWith('-')) throw new Error('Invalid reference');
 return (await git(repo, ['rev-parse', '--verify', `${ref}^{commit}`])).toString().trim();
}
async function scanGit(repo, ref, base, staged) {
 const entries = new Map();
 const add = raw => {
   for (const entry of raw.toString('utf8').split('\0').filter(Boolean)) {
     const m = entry.match(/^(\d+) (?:blob |commit )?([a-f0-9]+)(?: (\d+))?\t([\s\S]+)$/);
     if (!m) throw new Error('Unrecognized Git entry');
     if(m[3] && m[3]!=='0') throw new Error('Unmerged index');
     entries.set(`${m[2]}:${m[4]}`, {mode:m[1], oid:m[2], path:m[4]});
   }
 };
 if (staged) add(await git(repo, ['ls-files', '--stage', '-z']));
 else {
   const head = await hashRef(repo, ref);
   const commits = base ? (await git(repo, ['rev-list', `${await hashRef(repo,base)}..${head}`])).toString().trim().split('\n').filter(Boolean) : [];
   if (commits.length > 512) throw new Error('More than 512 outgoing commits; split and review the publication.');
   for (const commit of new Set([head, ...commits])) add(await git(repo, ['ls-tree', '-r', '-z', commit]));
 }
 const blobs = [...new Set([...entries.values()].filter(e=>e.mode !== '160000').map(e=>e.oid))];
 if (!blobs.length) throw new Error('No files to inspect');
 const sizes=[];
 for(let i=0;i<blobs.length;i+=32) sizes.push(...(await git(repo, ['cat-file','--batch-check'], {input:blobs.slice(i,i+32).join('\n')+'\n'})).toString().trim().split('\n'));
 const readable = [];
 for (const line of sizes) {
   const [oid,type,size] = line.split(' ');
   if (type !== 'blob' || !Number.isSafeInteger(Number(size))) throw new Error('Unreadable Git object');
   if (Number(size)>LIMIT) { for(const e of entries.values()) if(e.oid===oid) block(e.path,'oversized-file'); }
   else readable.push(oid);
 }
 for (let batchStart=0;batchStart<readable.length;batchStart+=32) {
 const batch=readable.slice(batchStart,batchStart+32);
 const output = await git(repo, ['cat-file','--batch'], {input:batch.join('\n')+'\n'});
 let offset = 0;
 for (const oid of batch) {
   const end = output.indexOf(10,offset);
   const [actual,type,size] = output.subarray(offset,end).toString().split(' ');
   if(actual!==oid || type!=='blob' || end<0) throw new Error('Git object mismatch');
   offset=end+1;const count=Number(size);
   if(offset+count>=output.length) throw new Error('Truncated Git object');
   const data=output.subarray(offset,offset+count);offset+=count+1;
   for(const e of entries.values()) if(e.oid===oid) scan(e.path,data,e.mode);
 }
 }
 for(const e of entries.values()) {
   if(e.mode==='160000' && (exceptions[e.path]?.gitObject!==e.oid || typeof exceptions[e.path]?.reason!=='string')) block(e.path,'unsupported-entry');
 }
}
function scanDirectory(root, path = root) {
 const stat = lstatSync(path); const name = relative(root,path).replaceAll('\\','/');
 if(/(^|\/)\.git(?:\/|$)/i.test(name)) {block(name,'private-path');return;}
 if(stat.isSymbolicLink()) {block(name,'unsupported-entry');return;}
 if(stat.isDirectory()) { for(const entry of readdirSync(path)) scanDirectory(root,join(path,entry)); }
 else if(!stat.isFile()) block(name,'unsupported-entry');
 else if(stat.size>LIMIT) block(name,'oversized-file');
 else scan(name,readFileSync(path));
}
try {
 try { exceptions = JSON.parse(readFileSync(join(here, 'publication-exceptions.json'), 'utf8')); }
 catch (error) { if (error.code !== 'ENOENT') throw error; }
 const args=process.argv.slice(2); const options={repo:process.cwd(),ref:'HEAD'};
 for(let i=0;i<args.length;i++) {
   const key=args[i].replace(/^--/,'');
   if(['staged','pre-push'].includes(key)) options[key]=true;
   else if(['repo','ref','base','directory'].includes(key) && args[i+1]) options[key]=args[++i];
   else throw new Error('Unknown or incomplete argument');
 }
 if(options.directory) scanDirectory(resolve(options.repo, options.directory));
 else if(options['pre-push']) {
   for(const line of readFileSync(0,'utf8').trim().split('\n').filter(Boolean)) {
     const [,local,,remote]=line.trim().split(/\s+/);
     if(!/^[a-f0-9]{40,64}$/.test(local||'') || !/^[a-f0-9]{40,64}$/.test(remote||'')) throw new Error('Invalid push input');
     if(/^0+$/.test(local)) continue;
     let base=remote;
     if(/^0+$/.test(remote)) base=(await git(options.repo,['merge-base',local,'refs/remotes/origin/main'])).toString().trim();
     await scanGit(options.repo,local,base,false);
   }
 } else await scanGit(options.repo,options.ref,options.base,options.staged);
 if(findings.size) { console.error('Publication blocked:\n'+[...findings].join('\n'));process.exitCode=1; }
 else console.log(`Publication check passed (${inspected} file versions).`);
} catch { console.error('Publication inspection failed. Check input, refs, file sizes and access; nothing was approved.');process.exitCode=2; }
