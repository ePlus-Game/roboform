import { createHash } from 'node:crypto';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

export const EXTENSION_ID = 'pnlccmojcmeohlpggmfnbbiapkmbliob';
const ABC = 'abcdefghijklmnop';

export function extensionIdFromKey(base64Key) {
  const keyHash = createHash('sha256').update(Buffer.from(base64Key, 'base64')).digest();
  return Array.from(keyHash.subarray(0, 16), byte => ABC[byte >> 4] + ABC[byte & 15]).join('');
}

export function crxZipPayload(contents) {
  if (contents.toString('ascii', 0, 4) !== 'Cr24' || contents.length < 16)
    throw new Error('Chrome Web Store did not return CRX file.');
  const version = contents.readUInt32LE(4);
  if (version !== 3) throw new Error(`Unsupported CRX version ${version}.`);
  const offset = 12 + contents.readUInt32LE(8);
  if (offset >= contents.length || contents.readUInt32LE(offset) !== 0x04034b50)
    throw new Error('CRX3 ZIP payload is invalid.');
  return contents.subarray(offset);
}

export async function installExtension() {
  // Official Chrome Web Store update service: never use unverified mirrors.
  const url = new URL('https://clients2.google.com/service/update2/crx');
  url.searchParams.set('response', 'redirect');
  url.searchParams.set('prod', 'chromium');
  url.searchParams.set('prodversion', '143.0.0.0');
  url.searchParams.set('acceptformat', 'crx3');
  url.searchParams.set('x', `id=${EXTENSION_ID}&installsource=ondemand&uc`);
  const response = await fetch(url, { redirect: 'follow', signal: AbortSignal.timeout(90_000),
    headers: { 'User-Agent': 'Mozilla/5.0 Chrome/143.0.0.0 Safari/537.36' } });
  if (!response.ok) throw new Error(`Chrome Web Store download failed (HTTP ${response.status}).`);
  const contents = Buffer.from(await response.arrayBuffer());
  if (contents.length > 35 * 1024 * 1024) throw new Error('Unexpected extension size.');
  const zip = crxZipPayload(contents);
  const directory = await mkdtemp(join(tmpdir(), 'roboform-ext-'));
  const archive = join(directory, 'extension.zip');
  const extensionDir = join(directory, 'unpacked');
  await mkdir(extensionDir);
  await writeFile(archive, zip);
  execFileSync('unzip', ['-q', '-o', archive, '-d', extensionDir], { timeout: 45_000 });
  const manifest = JSON.parse(await readFile(join(extensionDir, 'manifest.json'), 'utf8'));
  if (!manifest.key || extensionIdFromKey(manifest.key) !== EXTENSION_ID ||
      manifest.manifest_version !== 3 || manifest.background?.service_worker !== 'main.js') {
    throw new Error('Downloaded extension identity or manifest does not match expected RoboForm.');
  }
  console.log(`RoboForm extension v${manifest.version} downloaded and identity verified.`);
  return extensionDir;
}
