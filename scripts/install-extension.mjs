import { createHash } from 'node:crypto';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

export const EXTENSION_ID = 'pnlccmojcmeohlpggmfnbbiapkmbliob';
const ABC = 'abcdefghijklmnop';
// Public key from the supplied RoboForm 10.0.2.0 extension manifest.
// Chrome Web Store strips manifest.key from its CRX, but Chromium needs it
// to keep the same extension ID when loading the extracted directory.
const ROBOFORM_PUBLIC_KEY = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDAeBFO3sny3mtTlvQWOG2ijdmlg7yLpYWq6FvcoXkn2VMFM/r4I7Ko5gzxMekrF9fjljyuey4EDi68BboBSX8FoJogr6dBSmrJgc7ROZzyxMO0Fr2hZOFkswIslVbj2nQeSWq8EqFUUXO/Rt7NuRQijBk+q4qb/YUAhjbVtzDWmwIDAQAB';
const toId = bytes => Array.from(bytes, byte => ABC[byte >> 4] + ABC[byte & 15]).join('');

export function extensionIdFromKey(base64Key) {
  return toId(createHash('sha256').update(Buffer.from(base64Key, 'base64')).digest().subarray(0, 16));
}

function readVarint(buffer, offset) {
  let value = 0;
  let multiplier = 1;
  for (let i = 0; i < 8; i++) {
    if (offset >= buffer.length) throw new Error('Truncated CRX3 protobuf.');
    const byte = buffer[offset++];
    value += (byte & 0x7f) * multiplier;
    if (!(byte & 0x80)) return [value, offset];
    multiplier *= 128;
  }
  throw new Error('Invalid CRX3 protobuf varint.');
}

function protobufByteField(buffer, fieldNumber) {
  let offset = 0;
  while (offset < buffer.length) {
    let tag;
    [tag, offset] = readVarint(buffer, offset);
    const field = Math.floor(tag / 8);
    const wire = tag % 8;
    if (wire === 0) { [, offset] = readVarint(buffer, offset); continue; }
    if (wire === 1) { offset += 8; continue; }
    if (wire === 5) { offset += 4; continue; }
    if (wire !== 2) throw new Error('Unknown CRX3 protobuf wire type.');
    let length;
    [length, offset] = readVarint(buffer, offset);
    const end = offset + length;
    if (end > buffer.length) throw new Error('Truncated CRX3 protobuf bytes.');
    if (field === fieldNumber) return buffer.subarray(offset, end);
    offset = end;
  }
  return null;
}

export function getCrx3ExtensionId(contents) {
  if (contents.toString('ascii', 0, 4) !== 'Cr24' ||
      contents.length < 16 || contents.readUInt32LE(4) !== 3)
    throw new Error('Invalid CRX3 package.');
  const size = contents.readUInt32LE(8);
  if (12 + size > contents.length) throw new Error('Invalid CRX3 header length.');
  const header = contents.subarray(12, 12 + size);
  const signedData = protobufByteField(header, 10000);
  if (!signedData) throw new Error('CRX3 signed header data missing.');
  const crxIdBytes = protobufByteField(signedData, 1);
  if (!crxIdBytes || crxIdBytes.length !== 16) throw new Error('CRX3 extension id missing.');
  return toId(crxIdBytes);
}

export function crxZipPayload(contents) {
  if (contents.toString('ascii', 0, 4) !== 'Cr24' || contents.length < 16)
    throw new Error('Chrome Web Store did not return CRX file.');
  const version = contents.readUInt32LE(4);
  if (version !== 3) throw new Error(`Unsupported CRX version ${version}.`);
  const offset = 12 + contents.readUInt32LE(8);
  if (offset + 4 > contents.length || contents.readUInt32LE(offset) !== 0x04034b50)
    throw new Error('CRX3 ZIP payload is invalid.');
  return contents.subarray(offset);
}

export async function installExtension() {
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

  // Chrome Web Store CRX may omit manifest.key; validate the CRX3 signed
  // header's extension ID instead. Never accept a mismatched identity.
  const crxId = getCrx3ExtensionId(contents);
  if (crxId !== EXTENSION_ID) throw new Error(`Unexpected Chrome Web Store extension ID: ${crxId}`);
  const zip = crxZipPayload(contents);
  const directory = await mkdtemp(join(tmpdir(), 'roboform-ext-'));
  const archive = join(directory, 'extension.zip');
  const extensionDir = join(directory, 'unpacked');
  await mkdir(extensionDir);
  await writeFile(archive, zip);
  execFileSync('unzip', ['-q', '-o', archive, '-d', extensionDir], { timeout: 45_000 });
  const manifestPath = join(extensionDir, 'manifest.json');
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  if (extensionIdFromKey(ROBOFORM_PUBLIC_KEY) !== EXTENSION_ID)
    throw new Error('Bundled public key does not match expected RoboForm extension ID.');
  if (!manifest.key) {
    // Public key only: this is NOT a credential or private signing key.
    manifest.key = ROBOFORM_PUBLIC_KEY;
    await writeFile(manifestPath, JSON.stringify(manifest));
  }
  const fromKey = extensionIdFromKey(manifest.key);
  console.log(`Web Store RoboForm metadata: version=${manifest.version}, manifestV=${manifest.manifest_version}, hasKey=${!!manifest.key}, worker=${!!manifest.background?.service_worker}, crxId=${crxId}`);
  if ((fromKey && fromKey !== EXTENSION_ID) ||
      manifest.manifest_version !== 3 || !manifest.background?.service_worker) {
    throw new Error('Downloaded package is not a valid RoboForm MV3 extension.');
  }
  console.log(`Official RoboForm extension v${manifest.version} downloaded and identity verified.`);
  return extensionDir;
}
