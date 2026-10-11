import { readFile, readdir, mkdir, copyFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { createHash } from 'node:crypto';
const root = resolve(import.meta.dirname, '..');
const config = JSON.parse(await readFile(join(root, 'frontend/src-tauri/tauri.conf.json'), 'utf8'));
const version = config.version;
const bundle = join(root, 'frontend/src-tauri/target/release/bundle/nsis');
const installers = (await readdir(bundle)).filter(name => name.endsWith('-setup.exe'));
if (installers.length !== 1) throw new Error('Expected exactly one Windows installer');
const source = join(bundle, installers[0]);
const signature = (await readFile(source + '.sig', 'utf8')).trim();
if (!/^[A-Za-z0-9+/=]+$/.test(signature)) throw new Error('Missing valid updater signature');
const filename = `finesub-review-${version}-windows-x64-setup.exe`;
const out = join(root, 'output', `desktop-${version}`);
await mkdir(out, { recursive: true });
await copyFile(source, join(out, filename));
await writeFile(join(out, filename + '.sig'), signature + '\n');
const changelog = await readFile(join(root, 'CHANGELOG.md'), 'utf8');
const heading = `## 桌面版 ${version} —`;
if (!changelog.includes(heading)) throw new Error('Version has no changelog entry');
const notes = changelog.split(heading)[1].split('\n').slice(1).join('\n').split('\n## ')[0].trim();
const url = `https://github.com/Yuuu0109/finesub-review/releases/download/v${version}/${filename}`;
await writeFile(join(out, 'latest.json'), JSON.stringify({ version, notes, pub_date: new Date().toISOString(), platforms: { 'windows-x86_64': { signature, url } } }, null, 2) + '\n');
const lines = [];
for (const name of [filename, filename + '.sig', 'latest.json']) {
  lines.push(`${createHash('sha256').update(await readFile(join(out, name))).digest('hex')}  ${name}`);
}
await writeFile(join(out, 'SHA256SUMS.txt'), lines.join('\n') + '\n');
console.log(`Prepared signed Windows release ${version}: ${out}`);
