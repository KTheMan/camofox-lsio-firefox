#!/usr/bin/env bash
set -euo pipefail
# Reuse/focus the manual session instead of creating another window per click.
if ! node --input-type=module <<'NODE'
import fs from 'node:fs';
const key = (process.env.CAMOFOX_ACCESS_KEY_FILE ? fs.readFileSync(process.env.CAMOFOX_ACCESS_KEY_FILE,'utf8') : process.env.CAMOFOX_ACCESS_KEY)
  || (process.env.CAMOFOX_API_KEY_FILE ? fs.readFileSync(process.env.CAMOFOX_API_KEY_FILE,'utf8') : process.env.CAMOFOX_API_KEY);
if (!key?.trim()) process.exit(1);
const headers = {Authorization:`Bearer ${key.trim()}`,'Content-Type':'application/json'};
async function api(path, method='GET', body) {
  const response = await fetch('http://127.0.0.1:9377'+path,{method,headers,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(45000)});
  if (!response.ok) throw new Error('Browser unavailable');
  return response.json();
}
try {
  const {tabs=[]} = await api('/tabs?userId=selkies&sessionKey=desktop');
  const existing = tabs.find(tab=>tab.listItemId==='desktop');
  if (existing) await api('/tabs/'+existing.tabId+'/focus','POST',{userId:'selkies'});
  else await api('/tabs','POST',{userId:'selkies',sessionKey:'desktop'});
} catch { process.exit(1); }
NODE
then
  xmessage -center 'The shared browser is busy or unavailable. Finish any human handoff, then try again.'
  exit 1
fi
