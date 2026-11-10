// Public fixture keys/tokens for an isolated review network, never real Access.
import fs from 'node:fs';
import { generateKeyPairSync, sign } from 'node:crypto';
const directory = process.argv[2];
if (!directory) throw new Error('Supply a new test-fixture directory');
fs.mkdirSync(directory, { recursive: false, mode: 0o755 });
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'candidate-review', alg: 'RS256', use: 'sig' };
const token = (extra = {}) => {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: jwk.kid })).toString('base64url');
  const claims = Buffer.from(JSON.stringify({ iss: 'https://review.cloudflareaccess.com', aud: ['candidate-browser'], exp: Math.floor(Date.now()/1000)+3600, ...extra })).toString('base64url');
  return `${header}.${claims}.${sign('RSA-SHA256', Buffer.from(`${header}.${claims}`), privateKey).toString('base64url')}`;
};
fs.writeFileSync(`${directory}/jwks.json`, JSON.stringify({ keys: [jwk] }), { mode: 0o644 });
fs.writeFileSync(`${directory}/tokens.json`, JSON.stringify({ valid: token(), wrongAudience: token({ aud: ['other'] }), expired: token({ exp: 1 }) }), { mode: 0o644 });
console.log('Created dummy review signing fixtures; no private signing key was saved.');
