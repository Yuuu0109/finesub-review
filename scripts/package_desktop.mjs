import { readFile, mkdir, copyFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { createHash } from 'node:crypto';
const root = resolve(import.meta.dirname, '..');
const config = JSON.parse(await readFile(join(root, 'frontend/src-tauri/tauri.conf.json'), 'utf8'));
const version = config.version;
const out = join(root, 'output', `desktop-${version}`);
const changelog = await readFile(join(root, 'CHANGELOG.md'), 'utf8');
const heading = `## 桌面版 ${version} —`;
if (!changelog.includes(heading)) throw new Error('Version has no changelog entry');
const notes = changelog.split(heading)[1].split('\n').slice(1).join('\n').split('\n## ')[0].trim();
const portableSource = join(root, 'frontend/src-tauri/target/release/finesub-review-desktop.exe');
const portableName = `finesub-review-${version}-windows-x64-portable.exe`;
const portableSignature = (await readFile(portableSource + '.sig', 'utf8')).trim();
if (!/^[A-Za-z0-9+/=]+$/.test(portableSignature)) throw new Error('Missing portable signature');
await mkdir(out, { recursive: true });
await copyFile(portableSource, join(out, portableName));
await writeFile(join(out, portableName + '.sig'), portableSignature + '\n');
const portableUrl = `https://github.com/Yuuu0109/finesub-review/releases/download/v${version}/${portableName}`;
await writeFile(join(out, 'latest.json'), JSON.stringify({ version, notes, pub_date: new Date().toISOString(), platforms: { 'windows-x86_64-portable': { signature: portableSignature, url: portableUrl } } }, null, 2) + '\n');
const lines = [];
for (const name of [portableName, portableName + '.sig', 'latest.json']) {
  lines.push(`${createHash('sha256').update(await readFile(join(out, name))).digest('hex')}  ${name}`);
}
await writeFile(join(out, 'SHA256SUMS.txt'), lines.join('\n') + '\n');
console.log(`Prepared signed Windows portable release ${version}: ${out}`);
