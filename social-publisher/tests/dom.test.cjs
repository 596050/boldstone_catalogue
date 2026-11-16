const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto, createHash } = require('node:crypto');
const { File } = require('node:buffer');
const driver = fs.readFileSync(path.join(__dirname, '..', 'dom-driver.js'), 'utf8');

class Element {
  constructor(text = '', attrs = {}, tag = 'BUTTON') {
    this.innerText = text; this.attrs = { ...attrs }; this.tagName = tag;
    this.type = attrs.type; this.disabled = false; this.visible = true;
    this.clicked = 0; this.events = []; this.nodes = {}; this.complete = true;
    this.naturalWidth = 500; this.naturalHeight = 500;
  }
  getClientRects() { return this.visible ? [1] : []; }
  getAttribute(k) { return this.attrs[k] ?? null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  hasAttribute(k) { return k in this.attrs; }
  querySelectorAll(selector) { return this.nodes[selector] || []; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return this.parent || null; }
  click() { this.clicked++; if (this.attrs['aria-checked']) this.attrs['aria-checked'] = this.attrs['aria-checked'] === 'true' ? 'false' : 'true'; }
  matches(selector) {
    if (selector === 'a[href]') return this.tagName === 'A' && !!this.href;
    if (selector.includes('input[type="file"]')) return this.tagName === 'INPUT' && this.type === 'file';
    if (selector.includes('checkbox')) return this.tagName === 'INPUT' && this.type === 'checkbox';
    if (selector.startsWith('textarea,')) return this.tagName === 'TEXTAREA' || (this.tagName === 'INPUT' && this.type === 'text');
    return false;
  }
  dispatchEvent(e) { this.events.push(e.type); }
  focus() { this.focused = true; }
}
class Textarea extends Element {
  constructor(value = '') { super('', {}, 'TEXTAREA'); this._value = value; }
  get value() { return this._value; }
  set value(v) { this._value = v; }
}
class Input extends Element {
  constructor(type) { super('', { type }, 'INPUT'); this._value = ''; }
  get value() { return this._value; }
  set value(v) { this._value = v; }
}
class Transfer {
  constructor() { this.files = []; this.items = { add: f => this.files.push(f) }; }
}

function fixture() {
  const root = new Element('', {}, 'HTML'); root.setAttribute('data-boldstone-publisher', 'owner');
  const nodes = {};
  const state = { focus: false };
  const document = {
    documentElement: root,
    readyState: 'complete', title: 'Fixture', hasFocus: () => state.focus,
    querySelectorAll: s => nodes[s] || [], querySelector: s => (nodes[s] || [])[0] || null,
  };
  const context = vm.createContext({ document, location: { href: 'https://www.linkedin.com/sharing/compose', pathname: '/sharing/compose' },
    getComputedStyle: () => ({ visibility: 'visible' }), DataTransfer: Transfer, File,
    HTMLInputElement: Input, HTMLTextAreaElement: Textarea,
    Event: class { constructor(type) { this.type = type; } }, InputEvent: class { constructor(type) { this.type = type; } },
    crypto: webcrypto, atob: s => Buffer.from(s, 'base64').toString('binary'),
  });
  const run = request => JSON.parse(vm.runInContext(driver + '(' + JSON.stringify({ expectedURL: context.location.href, owner: 'owner', ...request }) + ')', context));
  return { nodes, root, state, context, document, run };
}

test('missing and ambiguous controls are held without clicking a fallback', () => {
  const f = fixture(), a = new Element('Next'), b = new Element('Next');
  f.nodes['button'] = [a, b];
  assert.equal(f.run({ op: 'click', locator: { selector: 'button', name: 'Next' } }).code, 'AMBIGUOUS_CONTROL');
  assert.equal(a.clicked + b.clicked, 0);
  assert.equal(f.run({ op: 'click', locator: { selector: '#absent' } }).code, 'CONTROL_MISSING');
});
test('generic operations cannot click Publish, Post or Share', () => {
  for (const name of ['Publish', 'Post', 'Share', 'Publish post', 'Schedule now']) {
    const f = fixture(), button = new Element(name); f.nodes['button'] = [button];
    assert.equal(f.run({ op: 'click', locator: { selector: 'button' } }).code, 'GUARDED_ACTION_REQUIRED');
    assert.equal(button.clicked, 0);
  }
});
test('the OS file picker cannot be opened by a generic click', () => {
  const f = fixture(), input = new Input('file'); f.nodes['input'] = [input];
  assert.equal(f.run({ op: 'click', locator: { selector: 'input' } }).code, 'GUARDED_ACTION_REQUIRED');
  assert.equal(input.clicked, 0);
  const add = new Element('Add media'); f.nodes['button'] = [add];
  assert.equal(f.run({ op: 'click', locator: { selector: 'button' } }).code, 'NATIVE_PICKER_FORBIDDEN');
});
test('foreground tabs and lost ownership are held', () => {
  const f = fixture(); f.nodes['button'] = [new Element('Next')]; f.state.focus = true;
  assert.equal(f.run({ op: 'click', locator: { selector: 'button' } }).code, 'FOREGROUND_TAB_PAUSED');
  f.state.focus = false; f.root.setAttribute('data-boldstone-publisher', 'someone-else');
  assert.equal(f.run({ op: 'click', locator: { selector: 'button' } }).code, 'TAB_OWNERSHIP_LOST');
});
test('URL changes are checked inside the same JS operation', () => {
  const f = fixture();
  assert.equal(f.run({ op: 'probe', expectedURL: 'https://www.linkedin.com/old/' }).code, 'TAB_NAVIGATED_EXTERNALLY');
});
test('checkboxes change idempotently and verify the actual checked state', () => {
  const f = fixture(), checkbox = new Element('Boldstone Sculpture', { 'aria-checked': 'false' }); f.nodes['#account'] = [checkbox];
  assert.equal(f.run({ op: 'set_checked', locator: { selector: '#account' }, value: true }).checked, true);
  f.run({ op: 'set_checked', locator: { selector: '#account' }, value: true });
  assert.equal(checkbox.clicked, 1);
});
test('textareas use the native setter, input/change events and exact readback', () => {
  const f = fixture(), area = new Textarea(''); f.nodes['#caption'] = [area];
  const text = 'Full caption\nWith another paragraph.';
  assert.equal(f.run({ op: 'set_text', locator: { selector: '#caption' }, value: text }).value, text);
  assert.deepEqual(area.events, ['input', 'change']);
});
test('whole-document selectors cannot be used as a publishing guard', () => {
  const f = fixture();
  assert.equal(f.run({ op: 'assert', checks: [{ locator: { selector: 'body' } }] }).code, 'UNSCOPED_LOCATOR');
});
test('a toast and an editor value cannot substitute for full native caption readback', () => {
  const f = fixture(), post = new Element('Sally Price\nOnly the first line', {}, 'ARTICLE');
  f.nodes['#post'] = [post];
  const author = new Element('Sally Price', {}, 'A'), photo = new Element('', {}, 'IMG');
  const caption = new Element('Only the first line',{},'P');
  post.nodes['.author'] = [author]; post.nodes['.post-photo'] = [photo]; post.nodes['a[href]'] = []; post.nodes['.caption']=[caption];
  const request = { op: 'readback', root: { selector: '#post' }, caption: 'Only the first line\nThe lost second line.', captionSelectors:['.caption'], author: { selector: '.author', name: 'Sally Price' }, photoSelector: '.post-photo' };
  assert.equal(f.run(request).code, 'NATIVE_CAPTION_MISMATCH');
  post.innerText = 'Sally Price\nOnly the first line\nThe lost second line.';
  caption.innerText='Only the first line\nThe lost second line.';
  author.innerText = 'Another person'; assert.equal(f.run(request).code, 'NATIVE_AUTHOR_MISMATCH');
  author.innerText = 'Sally Price'; photo.naturalWidth = 0; assert.equal(f.run(request).code, 'NATIVE_PHOTO_MISMATCH');
  photo.naturalWidth = 500; assert.equal(f.run(request).ok, true);
});
test('matching caption text in a comment cannot substitute for the post caption', () => {
  const f=fixture(), post=new Element('Actual caption\nComment: Complete expected caption',{},'ARTICLE'), caption=new Element('Actual caption',{},'P');
  f.nodes['#post']=[post]; post.nodes['.caption']=[caption];
  assert.equal(f.run({op:'readback',root:{selector:'#post'},caption:'Complete expected caption',captionSelectors:['.caption'],author:[],photoSelector:'.photo'}).code,'NATIVE_CAPTION_MISMATCH');
});
test('discovery requires one exact native permalink', () => {
  const f = fixture(), scope = new Element('', {}, 'MAIN'); f.nodes['main'] = [scope];
  const a = new Element('', {}, 'A'); a.href = 'https://www.instagram.com/p/one/';
  scope.nodes['a[href]'] = [a];
  assert.equal(f.run({ op: 'discover', pattern: '^https://www\\.instagram\\.com/p/' }).url, a.href);
  const b = new Element('', {}, 'A'); b.href = 'https://www.instagram.com/p/two/'; scope.nodes['a[href]'].push(b);
  assert.equal(f.run({ op: 'discover', pattern: '^https://www\\.instagram\\.com/p/' }).code, 'AMBIGUOUS_NATIVE_POST');
});
test('image bytes are SHA-256 checked before a background file-input upload', async () => {
  const f = fixture(), input = new Input('file'); input.visible = false; f.nodes['#file'] = [input];
  const bytes = Buffer.from('original photograph bytes'); const sha = createHash('sha256').update(bytes).digest('hex');
  const common = { job: 'one', mediaSha256: sha };
  assert.equal(f.run({ op: 'upload_begin', locator: { selector: '#file', hidden: true }, name: 'original.png', type: 'image/png', size: bytes.length, ...common }).ok, true);
  f.run({ op: 'upload_chunk', index: 0, data: bytes.toString('base64'), ...common });
  assert.equal(f.run({ op: 'upload_finish', chunks: 1, ...common }).status, 'HASHING');
  for (let i = 0; i < 30 && f.run({ op: 'upload_status', ...common }).status === 'HASHING'; i++) await new Promise(resolve => setTimeout(resolve, 2));
  assert.equal(f.run({ op: 'upload_status', ...common }).status, 'HASH_VERIFIED');
  assert.equal(f.run({ op: 'upload_commit', ...common }).sha256, sha);
  assert.equal(input.files[0].name, 'original.png'); assert.equal(input.clicked, 0);
  assert.deepEqual(input.events, ['input', 'change']);
});
test('wrong image hashes cannot be committed', async () => {
  const f = fixture(), input = new Input('file'); f.nodes['#file'] = [input];
  const common = { job: 'one', mediaSha256: '0'.repeat(64) }, bytes = Buffer.from('wrong');
  f.run({ op: 'upload_begin', locator: { selector: '#file' }, name: 'wrong.png', type: 'image/png', size: bytes.length, ...common });
  f.run({ op: 'upload_chunk', index: 0, data: bytes.toString('base64'), ...common }); f.run({ op: 'upload_finish', chunks: 1, ...common });
  for (let i = 0; i < 30 && f.run({ op: 'upload_status', ...common }).status === 'HASHING'; i++) await new Promise(resolve => setTimeout(resolve, 2));
  assert.equal(f.run({ op: 'upload_commit', ...common }).code, 'UPLOAD_HASH_NOT_VERIFIED');
  assert.equal(input.files, undefined);
});
test('the guarded submission rechecks the caption and permits only one click', () => {
  const f = fixture(), button = new Element('Post'), caption = new Textarea('Full caption'), photo = new Element('', {}, 'IMG');
  f.nodes['#post'] = [button]; f.nodes['#caption'] = [caption]; f.nodes['#photo'] = [photo];
  f.context.__boldstoneMedia = { job: 'one', sha256: 'verified-image', committed: true };
  const request = { op: 'submit', job: 'one', mediaSha256: 'verified-image', submit: { selector: '#post' },
    checks: [{ locator: { selector: '#caption' }, text: 'Full caption' }, { locator: { selector: '#photo' }, image: true }] };
  caption.value = ''; assert.equal(f.run(request).code, 'TEXT_READBACK_CHANGED'); assert.equal(button.clicked, 0);
  caption.value = 'Full caption'; assert.equal(f.run(request).status, 'CLICKED_UNCONFIRMED');
  assert.equal(f.run(request).code, 'SUBMIT_ALREADY_CLICKED'); assert.equal(button.clicked, 1);
});
test('a composer with retained text or an uploaded preview is never considered clean', () => {
  const f=fixture(), area=new Textarea('Unsaved caption'), photo=new Element('',{},'IMG');
  f.nodes['#caption']=[area]; f.nodes['#preview']=[];
  const request={op:'clean_state',caption:{selector:'#caption'},preview:{selector:'#preview'}};
  assert.equal(f.run(request).clean,false);
  area.value=''; f.nodes['#preview']=[photo]; assert.equal(f.run(request).clean,false);
  f.nodes['#preview']=[]; assert.equal(f.run(request).clean,true);
});

