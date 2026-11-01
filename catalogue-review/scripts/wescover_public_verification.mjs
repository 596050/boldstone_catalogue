import fs from 'node:fs/promises';

// Execute inside CUA only. Verify observed public links through rendered UI.
export function wescoverPublicVerification({tab, directory}) {
  const read = async name => JSON.parse(await fs.readFile(`${directory}/${name}`, 'utf8'));
  async function next() {
    const source = await read('enrichment-receipts.json');
    const links = (await read('public-creator-178-links.json')).rows;
    const receipts = await read('public-product-readbacks.json').catch(error => {
      if (error.code === 'ENOENT') return [];
      throw error;
    });
    const record = source.find(row => !receipts.some(done => done.sku === row.sku));
    if (!record) return {complete: true, count: receipts.length};
    const matches = links.filter(link => link.title === `Product, ${record.title}`);
    if (matches.length !== 1) throw Error(`Ambiguous public title: ${record.sku}`);
    const link = matches[0];
    const savedId = new URL(record.url).searchParams.get('item');
    const publicId = link.url.split('--').pop();
    if (savedId !== 'new' && savedId !== publicId) throw Error('Native/public identity mismatch');
    await tab.goto(link.url);
    await tab.playwright.getByRole('heading', {name: `${record.title} - Wall Hangings`, exact: true})
      .waitFor({state: 'visible', timeoutMs: 10000});
    await tab.playwright.domSnapshot();
    const details = tab.playwright.getByRole('button', {name: 'Item details ', exact: true});
    if (await details.isVisible()) await details.click();
    const snapshot = await tab.playwright.domSnapshot();
    const main = await tab.playwright.getByRole('main').innerText();
    const checks = {
      sku: main.includes(`(${record.sku})`),
      gypsum: main.includes('Made from a gypsum-based material.'),
      dispatch: main.includes('Within 10 working days.'),
      individual: main.includes('1 individually described sculpture or panel'),
      checkout: await tab.playwright.getByRole('button', {name: 'Checkout', exact: true}).isVisible(),
      add_to_bag: await tab.playwright.getByRole('button', {name: 'Add to Bag', exact: true}).isVisible(),
    };
    if (Object.values(checks).some(value => !value)) {
      await fs.writeFile(`${directory}/public-check-exception-${record.sku}.txt`, snapshot);
      return {sku: record.sku, checks, exception: true};
    }
    const receipt = {at: new Date().toISOString(), sku: record.sku, title: record.title,
      url: link.url, native_item_id: publicId, checks,
      verification_context: 'Customer-facing product page in the signed-in creator browser; anonymous access not independently verified'};
    receipts.push(receipt);
    await fs.writeFile(`${directory}/public-product-readback-${record.sku}.txt`, main);
    const path = `${directory}/public-product-readbacks.json`;
    await fs.writeFile(path + '.tmp', JSON.stringify(receipts, null, 2) + '\n');
    await fs.rename(path + '.tmp', path);
    return {sku: record.sku, checked: receipts.length, remaining: source.length - receipts.length};
  }
  return {next};
}
