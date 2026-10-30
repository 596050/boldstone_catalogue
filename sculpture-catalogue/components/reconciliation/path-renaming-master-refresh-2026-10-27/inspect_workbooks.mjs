import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, '../../..');
const pointer = JSON.parse(await fs.readFile(path.join(base, 'current-master.json'), 'utf8'));
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(base, pointer.preferred_review_workbook)));
await fs.mkdir(path.join(here, 'previews'), { recursive: true });
const overview = await book.inspect({ kind: 'region', sheetId: 'Wall Sculptures', range: 'L8:M12', maxChars: 1400 });
const styles = await book.inspect({ kind: 'computedStyle', sheetId: 'Wall Sculptures', range: 'L8:M10', maxChars: 1800 });
const hyperlinks = book.help('*', { search: 'hyperlink', include: 'index,examples,notes', maxChars: 4500 });
await fs.writeFile(path.join(here, 'source-workbook-inspect.ndjson'), overview.ndjson + '\n' + styles.ndjson);
await fs.writeFile(path.join(here, 'hyperlink-api-help.ndjson'), hyperlinks.ndjson);
const preview = await book.render({ sheetName: 'Wall Sculptures', range: 'L8:M12', scale: 1.4, format: 'png' });
await fs.writeFile(path.join(here, 'previews/source-image-links.png'), new Uint8Array(await preview.arrayBuffer()));
console.log(hyperlinks.ndjson);
console.log('SOURCE_WORKBOOK_INSPECTED_AND_RENDERED_NO_EXPORT');
