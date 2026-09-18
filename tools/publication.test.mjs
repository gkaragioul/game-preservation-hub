import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, writeFileSync, mkdirSync, rmSync, copyFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
const guard = new URL('./check-publication.mjs', import.meta.url).pathname.replace(/^\/([A-Z]:)/i, '$1');
function fixture(t) {
  const dir = mkdtempSync(join(tmpdir(), 'publication-test-'));
  t.after(() => rmSync(dir, {recursive:true, force:true}));
  return dir;
}
function run(dir, ...args) { return spawnSync(process.execPath,[guard,'--repo',dir,...args],{encoding:'utf8'}); }
function git(dir,...args) { const r=spawnSync('git',['-C',dir,...args],{encoding:'utf8'}); assert.equal(r.status,0,r.stderr);return r.stdout.trim(); }
function repo(t) { const dir=fixture(t);git(dir,'init');git(dir,'config','user.name','Test');git(dir,'config','user.email','test@example.invalid');writeFileSync(join(dir,'README.md'),'public project');git(dir,'add','.');git(dir,'commit','-m','baseline');return dir; }
test('allows ordinary public docs and inert example env files',t=>{
 const dir=fixture(t);writeFileSync(join(dir,'README.md'),'Public compatibility report');writeFileSync(join(dir,'.env.example'),'NAME=replace-me');assert.equal(run(dir,'--directory','.').status,0);
});
test('rejects private links and credentials without printing contents',t=>{
 const dir=fixture(t);const marker='gh'+'p_'+'a'.repeat(36);writeFileSync(join(dir,'notes.txt'),'https://app.'+'notion.com/p/'+'a'.repeat(32)+' '+marker);const r=run(dir,'--directory','.');assert.equal(r.status,1);assert.match(r.stderr,/private-link|credential/);assert.ok(!r.stderr.includes(marker));assert.ok(!r.stderr.includes('a'.repeat(32)));
});
test('rejects private working directories and env files',t=>{
 const dir=fixture(t);mkdirSync(join(dir,'.porting'));writeFileSync(join(dir,'.porting','notes.txt'),'internal');writeFileSync(join(dir,'.env.local'),'SETTING=value');assert.equal(run(dir,'--directory','.').status,1);
});
test('rejects a copied Git database even when its compressed content has no markers',t=>{
 const dir=fixture(t);mkdirSync(join(dir,'.git','objects','pack'),{recursive:true});writeFileSync(join(dir,'.git','objects','pack','example.pack'),'compressed history');const r=run(dir,'--directory','.');assert.equal(r.status,1);assert.match(r.stderr,/private-path/);
});
test('rejects uninspected archives, executable artifacts and source maps',t=>{
 for(const name of ['release.zip','runtime.exe','bundle.js.map']) {const dir=fixture(t);writeFileSync(join(dir,name),Buffer.from([80,75,3,4]));const r=run(dir,'--directory','.');assert.equal(r.status,1);assert.match(r.stderr,/artifact-needs-review/);}
});
test('checks staged content rather than a sanitized working copy',t=>{
 const dir=repo(t);writeFileSync(join(dir,'notes.txt'),'https://app.'+'notion.com/p/'+'b'.repeat(32));git(dir,'add','.');writeFileSync(join(dir,'notes.txt'),'clean');assert.equal(run(dir,'--staged').status,1);
});
test('checks secrets committed then removed inside outgoing history',t=>{
 const dir=repo(t);const base=git(dir,'rev-parse','HEAD');writeFileSync(join(dir,'notes.txt'),'gh'+'p_'+'b'.repeat(36));git(dir,'add','.');git(dir,'commit','-m','bad');git(dir,'rm','notes.txt');git(dir,'commit','-m','remove');assert.equal(run(dir,'--base',base,'--ref','HEAD').status,1);
});
test('fails closed for missing refs or artifact directories',t=>{
 const dir=repo(t);assert.notEqual(run(dir,'--ref','missing-ref').status,0);assert.notEqual(run(dir,'--directory','missing-dir').status,0);
});
test('rejects UTF-16 private links',t=>{
 const dir=fixture(t);writeFileSync(join(dir,'notes.txt'),Buffer.from('https://app.'+'notion.com/p/'+'c'.repeat(32),'utf16le'));assert.equal(run(dir,'--directory','.').status,1);
});
test('rejects big-endian UTF-16 and private implementation signatures',t=>{
 const dir=fixture(t);writeFileSync(join(dir,'notes.txt'),Buffer.from('https://app.'+'notion.com/p/'+'d'.repeat(32),'utf16le').swap16());const r=run(dir,'--directory','.');assert.equal(r.status,1);assert.match(r.stderr,/private-link/);
 writeFileSync(join(dir,'notes.txt'),'PPC_'+'CALL_INDIRECT_FUNC');assert.match(run(dir,'--directory','.').stderr,/private-core/);
});
test('git symlinks are rejected without following their target',t=>{
 const dir=repo(t);const oid=git(dir,'hash-object','README.md');git(dir,'update-index','--add','--cacheinfo',`120000,${oid},link`);const r=run(dir,'--staged');assert.equal(r.status,1);assert.match(r.stderr,/unsupported-entry/);
});
test('exceptions bind exact bytes and do not permit changed files',t=>{
 const dir=fixture(t),policy=fixture(t);copyFileSync(guard,join(policy,'check-publication.mjs'));const content=Buffer.from('fixture');writeFileSync(join(dir,'old.zip'),content);
 writeFileSync(join(policy,'publication-exceptions.json'),JSON.stringify({'old.zip':{sha256:createHash('sha256').update(content).digest('hex'),rules:['artifact'],reason:'reviewed fixture'}}));
 const check=()=>spawnSync(process.execPath,[join(policy,'check-publication.mjs'),'--repo',dir,'--directory','.'],{encoding:'utf8'});
 assert.equal(check().status,0);writeFileSync(join(dir,'old.zip'),'changed');assert.equal(check().status,1);
});
test('new branch pre-push scans committed-then-removed credentials',t=>{
 const dir=repo(t);git(dir,'update-ref','refs/remotes/origin/main','HEAD');writeFileSync(join(dir,'notes'),'gh'+'p_'+'c'.repeat(36));git(dir,'add','.');git(dir,'commit','-m','bad');git(dir,'rm','notes');git(dir,'commit','-m','remove');const oid=git(dir,'rev-parse','HEAD');
 const r=spawnSync(process.execPath,[guard,'--repo',dir,'--pre-push'],{input:`refs/heads/test ${oid} refs/heads/test ${'0'.repeat(40)}\n`,encoding:'utf8'});assert.equal(r.status,1);assert.match(r.stderr,/credential/);
});
