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
  getBoundingClientRect() { return {left:10,top:20,width:100,height:80}; }
  contains(e) { return e===this || e.parentElement===this; }
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
    if (selector.startsWith('textarea,')) return this.tagName === 'TEXTAREA' || (this.tagName === 'INPUT' && ['text','url'].includes(this.type));
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
  constructor() { this.files = []; this.data={}; this.items = { add: f => this.files.push(f) }; }
  setData(type,value) {this.data[type]=value;}
  getData(type) {return this.data[type]||'';}
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
    URL, navigator:{userActivation:{isActive:false}},
    getComputedStyle: e => ({ visibility: 'visible', opacity:e.opacity??'1' }), DataTransfer: Transfer, File,
    HTMLInputElement: Input, HTMLTextAreaElement: Textarea,
    Event: class { constructor(type) { this.type = type; } }, InputEvent: class { constructor(type) { this.type = type; } },
    MouseEvent:class {constructor(type,options){this.type=type;Object.assign(this,options);}},
    DragEvent:class {constructor(type,options){this.type=type;Object.assign(this,options);}},
    KeyboardEvent:class {constructor(type,options){this.type=type;Object.assign(this,options);}},
    FocusEvent:class {constructor(type,options){this.type=type;Object.assign(this,options);}},
    ClipboardEvent: class {constructor(type,options){this.type=type;Object.assign(this,options);this.defaultPrevented=false;}preventDefault(){this.defaultPrevented=true;}},
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
  for (const name of ['Publish', 'Post', 'Share', 'Publish post', 'Schedule now', 'Create ad', 'Boost', 'Promote']) {
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
test('ordinary DOM navigation does not use the Chrome URL setter', () => {
  const f=fixture();const targets=[];f.context.location.assign=url=>targets.push(url);
  const result=f.run({op:'navigate',url:'https://www.linkedin.com/feed/'});
  assert.equal(result.status,'NAVIGATION_REQUESTED');assert.deepEqual(targets,['https://www.linkedin.com/feed/']);
  assert.equal(f.run({op:'navigate',url:'javascript:alert(1)'}).code,'WRONG_DESTINATION');
});
test('upload preparation cannot open a picker with transient user activation', () => {
  const f=fixture(), button=new Element('Media');f.nodes['#media']=[button];
  f.context.navigator.userActivation.isActive=true;
  assert.equal(f.run({op:'prepare_upload',locator:{selector:'#media'}}).code,'USER_ACTIVATION_ACTIVE');assert.equal(button.clicked,0);
});
test('opening the composer is separate from the guarded publication click', () => {
  const f=fixture(), button=new Element('Start a post');f.nodes['#start']=[button];
  assert.equal(f.run({op:'click',locator:{selector:'#start'}}).ok,true);assert.equal(button.clicked,1);
});
test('Google Add post opens only the observed business posts inventory', () => {
  const f=fixture(), add=new Element('Add post');f.nodes['button']=[add];f.nodes.h1=[new Element('Your posts',{},'H1')];
  f.context.location.href='https://www.google.com/local/business/15009857378722117958/promote/updates?hl=en';
  assert.equal(f.run({op:'click',locator:{selector:'button'}}).ok,true);assert.equal(add.clicked,1);
  const post=new Element('Post');f.nodes['button']=[post];
  assert.equal(f.run({op:'click',locator:{selector:'button'}}).code,'GUARDED_ACTION_REQUIRED');assert.equal(post.clicked,0);
});
test('Google composer opening still rejects another route, host or missing inventory heading', () => {
  for(const url of ['https://www.google.com/search?q=Boldstone','https://example.com/local/business/15009857378722117958/promote/updates']){
    const f=fixture(), add=new Element('Add post');f.nodes.button=[add];f.nodes.h1=[new Element('Your posts',{},'H1')];f.context.location.href=url;
    assert.equal(f.run({op:'click',locator:{selector:'button'}}).code,'GUARDED_ACTION_REQUIRED');assert.equal(add.clicked,0);
  }
  const f=fixture(), add=new Element('Add post');f.nodes.button=[add];f.context.location.href='https://www.google.com/local/business/15009857378722117958/promote/updates';
  assert.equal(f.run({op:'click',locator:{selector:'button'}}).code,'GUARDED_ACTION_REQUIRED');assert.equal(add.clicked,0);
});
test('Google account path guards reject a different location even when the visible heading matches', () => {
  const f=fixture();f.nodes.h1=[new Element('Add post',{},'H1')];f.context.location.pathname='/local/business/999/promote/updates/add';
  assert.equal(f.run({op:'assert',checks:[{locator:{selector:'h1'},url_path_prefix:'/local/business/15009857378722117958/'}]}).code,'WRONG_SELECTED_ACCOUNT');
});
test('product button URL fields accept an exact HTTPS destination and reject executable or credential-bearing URLs', () => {
  const f=fixture(), input=new Input('url');f.nodes['input']=[input];const url='https://boldstonesculpture.com/buy/p/example?utm_source=google_business_profile';
  assert.equal(f.run({op:'set_text',locator:{selector:'input'},value:url}).ok,true);assert.equal(input.value,url);
  for(const bad of ['javascript:alert(1)','https://user:secret@example.com/']){
    assert.equal(f.run({op:'set_text',locator:{selector:'input'},value:bad}).code,'WRONG_DESTINATION');assert.equal(input.value,url);
  }
});
test('Google SVG photograph guards require a decoded image bound to this job and source hash', () => {
  const f=fixture(), photo=new Element('',{href:'blob:https://www.google.com/photo-one'},'image');photo.localName='image';photo.namespaceURI='http://www.w3.org/2000/svg';f.nodes['#photo']=[photo];
  f.context.location.href='https://www.google.com/local/business/123/promote/updates/add';
  f.context.Image=class {set src(value){this.naturalWidth=1254;this.naturalHeight=1254;this.onload();}};
  const check={locator:{selector:'#photo'},image:true,svg_image:true},context={job:'one',mediaSha256:'hash'};
  assert.equal(f.run({op:'assert',checks:[check],...context}).code,'PHOTO_NOT_LOADED');
  assert.equal(f.run({op:'probe_svg_photo',locator:{selector:'#photo'},...context}).ok,true);
  assert.equal(f.run({op:'assert',checks:[check],...context}).checks[0].photo.width,1254);
  assert.equal(f.run({op:'assert',checks:[check],...context,job:'other'}).code,'PHOTO_NOT_LOADED');
  photo.attrs.href='blob:https://www.google.com/photo-two';
  assert.equal(f.run({op:'assert',checks:[check],...context}).code,'PHOTO_NOT_LOADED');
});
test('SVG photograph probes reject foreign sources and non-Google editor pages', () => {
  const f=fixture(), photo=new Element('',{href:'https://example.com/photo.png'},'image');photo.localName='image';photo.namespaceURI='http://www.w3.org/2000/svg';f.nodes['#photo']=[photo];
  f.context.location.href='https://www.google.com/local/business/123/promote/updates/add';
  assert.equal(f.run({op:'probe_svg_photo',locator:{selector:'#photo'},job:'one',mediaSha256:'hash'}).code,'PHOTO_SOURCE_INVALID');
  photo.attrs.href='blob:https://www.google.com/photo-one';f.context.location.href='https://www.linkedin.com/sharing/compose';
  assert.equal(f.run({op:'probe_svg_photo',locator:{selector:'#photo'},job:'one',mediaSha256:'hash'}).code,'PHOTO_ELEMENT_REQUIRED');
});
test('existing post editors open without granting a publication or advertising click', () => {
  const f=fixture();
  for (const name of ['Manage post','Edit post','Edit Post']) {
    const button=new Element(name);f.nodes['#edit']=[button];
    assert.equal(f.run({op:'click',locator:{selector:'#edit'}}).ok,true);
    assert.equal(button.clicked,1);
  }
  const menu=new Element('Actions for this post',{'aria-haspopup':'menu'});f.nodes['#menu']=[menu];
  assert.equal(f.run({op:'click',locator:{selector:'#menu'}}).ok,true);
  for (const name of ['Post','Publish','Boost post','Create ad']) {
    const button=new Element(name);f.nodes['#commit']=[button];
    assert.equal(f.run({op:'click',locator:{selector:'#commit'}}).code,'GUARDED_ACTION_REQUIRED');
    assert.equal(button.clicked,0);
  }
});
test('multi-select destinations use their exposed selected state', () => {
  const f=fixture(), option=new Element('boldstonesculpture',{'aria-selected':'true'});f.nodes['#option']=[option];
  assert.equal(f.run({op:'assert',checks:[{locator:{selector:'#option'},checked:true}]}).ok,true);
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
test('rich text uses the editor paste handler and verifies every caption line',()=>{
  const f=fixture(), editor=new Element('',{},'DIV');editor.isContentEditable=true;f.nodes['#editor']=[editor];
  f.document.createRange=()=>({selectNodeContents(){}});
  f.context.window={getSelection:()=>({removeAllRanges(){},addRange(){}})};
  f.document.execCommand=()=>{throw new Error('The paste method must not use insertText');};
  editor.dispatchEvent=event=>{editor.innerText=event.clipboardData.getData('text/plain');event.preventDefault();};
  const caption='First paragraph\n\nSecond paragraph\n\nhttps://example.com/product';
  assert.equal(f.run({op:'set_text',method:'paste',locator:[{selector:'#editor'}],value:caption}).value,caption);
  editor.dispatchEvent=event=>{editor.innerText='Only the final line';event.preventDefault();};
  assert.equal(f.run({op:'set_text',method:'paste',locator:[{selector:'#editor'}],value:'Different first line\nFinal line'}).code,'EDITOR_READBACK_FAILED');
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
function authoredPhotoFixture() {
  const f=fixture(), post=new Element('',{},'ARTICLE'), caption=new Element('Complete authored caption',{},'P');
  const author=new Element('Sally Price',{},'A'), photo=new Element('',{alt:'Exact authored sculpture description'},'IMG');
  f.context.location.href='https://www.linkedin.com/feed/update/urn:li:activity:12345/';
  f.context.location.pathname='/feed/update/urn:li:activity:12345/';
  photo.src='https://media.licdn.com/dms/image/v2/asset/feedshare-shrink_800/photo';
  f.nodes['#post']=[post];post.nodes['.caption']=[caption];post.nodes['.author']=[author];post.nodes['img']=[photo];post.nodes['a[href]']=[];
  const request={op:'readback',root:{selector:'#post'},caption:'Complete authored caption',captionSelectors:['.caption'],
    author:{selector:'.author',name:'Sally Price'},photoSelector:'.previous-photo-markup',linkedinPhotoAlt:'Exact authored sculpture description'};
  return {...f,post,photo,request};
}
test('new LinkedIn photo markup requires the exact authored alt and a native feedshare image',()=>{
  const f=authoredPhotoFixture(), r=f.run(f.request);
  assert.equal(r.ok,true);
  assert.equal(r.photo.alt,f.request.linkedinPhotoAlt);
  assert.equal(r.photo.identity_method,'exact authored alt and native LinkedIn feedshare image');
  f.photo.attrs.alt='Different sculpture';assert.equal(f.run(f.request).code,'NATIVE_PHOTO_MISMATCH');
});
test('profile photographs and foreign image hosts cannot replace a LinkedIn post photo',()=>{
  const f=authoredPhotoFixture();
  f.photo.src='https://media.licdn.com/dms/image/v2/asset/profile-displayphoto-scale_100_100/photo';
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_MISMATCH');
  f.photo.src='https://media.licdn.com.attacker.example/dms/image/v2/asset/feedshare-shrink_800/photo';
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_MISMATCH');
});
test('the same photo matching both routes is counted once, while duplicate photos remain ambiguous',()=>{
  const f=authoredPhotoFixture();f.post.nodes['.previous-photo-markup']=[f.photo];
  assert.equal(f.run(f.request).ok,true);
  const second=new Element('',{alt:f.request.linkedinPhotoAlt},'IMG');second.src=f.photo.src;f.post.nodes['img'].push(second);
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_MISMATCH');
});
test('unloaded images and missing caption or author evidence still hold the new LinkedIn route',()=>{
  const f=authoredPhotoFixture();f.photo.naturalWidth=0;
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_MISMATCH');f.photo.naturalWidth=500;
  f.post.nodes['.caption'][0].innerText='Incomplete';assert.equal(f.run(f.request).code,'NATIVE_CAPTION_MISMATCH');
  f.post.nodes['.caption'][0].innerText=f.request.caption;f.post.nodes['.author'][0].innerText='Another person';
  assert.equal(f.run(f.request).code,'NATIVE_AUTHOR_MISMATCH');
});
test('the authored LinkedIn image route cannot be used on a feed or another platform',()=>{
  const f=authoredPhotoFixture();f.context.location.href='https://www.linkedin.com/feed/foryou/';
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_SCOPE_MISSING');
  f.context.location.href='https://www.facebook.com/BoldstoneSculpture/posts/12345';
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_SCOPE_MISSING');
  f.context.location.href='http://www.linkedin.com/feed/update/urn:li:activity:12345/';
  assert.equal(f.run(f.request).code,'NATIVE_PHOTO_SCOPE_MISSING');
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
test('a helper receipt needs its matching document marker and a loaded preview', () => {
  const f=fixture(), id='1'.repeat(32), sha='a'.repeat(64);
  const receipt={ok:true,request_id:id,sha256:sha,phase:'FILE_EVENTS_DISPATCHED',method:'chrome-main-world-file-input',name:'original.png',size:10};
  const request={op:'adopt_upload',job:'one',mediaSha256:sha,receipt,preview:[{selector:'#preview'}]};
  assert.equal(f.run(request).code,'UPLOAD_HELPER_DOCUMENT_MISMATCH');
  f.root.setAttribute('data-boldstone-upload-'+id,JSON.stringify(receipt));
  assert.equal(f.run(request).code,'CONTROL_MISSING');
  const preview=new Element('',{},'IMG');preview.naturalWidth=0;f.nodes['#preview']=[preview];
  assert.equal(f.run(request).code,'PHOTO_NOT_LOADED');
  assert.equal(f.run({op:'upload_status',job:'one'}).committed,false);
  preview.naturalWidth=500;
  assert.equal(f.run(request).status,'PHOTO_PREVIEW_CONFIRMED');
  assert.equal(f.run({op:'upload_status',job:'one'}).method,'helper');
  assert.equal(f.run({...request,mediaSha256:'b'.repeat(64)}).code,'UPLOAD_HELPER_RECEIPT_INVALID');
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


test('background typeahead activates only its DOM field and mouse selection cannot publish', () => {
  const f=fixture(), input=new Input('text');input.setAttribute('role','combobox');f.nodes['#query']=[input];
  assert.equal(f.run({op:'set_text',locator:{selector:'#query'},value:'White relief',focus:true,typeahead:true}).ok,true);
  assert.equal(input.focused,true);assert.ok(input.events.includes('focusin'));assert.ok(input.events.includes('keydown'));
  const publish=new Element('Publish');f.nodes['#publish']=[publish];
  assert.equal(f.run({op:'click',locator:{selector:'#publish'},method:'mouse'}).code,'GUARDED_ACTION_REQUIRED');
  assert.deepEqual(publish.events,[]);
});
test('photo tag placement cannot send mouse events to a named publication button', () => {
  const f=fixture(), panel=new Element('Tags',{},'DIV'), photo=new Element('',{},'IMG'), publish=new Element('Publish');
  photo.parent=panel;publish.parent=panel;f.nodes['#photo']=[photo];f.nodes['#publish']=[publish];
  assert.equal(f.run({op:'click_photo_point',locator:{selector:'#photo'},target:{selector:'#publish'},x:.5,y:.5}).code,'PHOTO_POINT_TARGET_INVALID');
  assert.deepEqual(publish.events,[]);
});
test('a saved product attestation requires the selected name, price and one marker, then stays job-bound', () => {
  const f=fixture(), panel=new Element('Tags',{},'DIV'), heading=new Element('White relief',{},'SPAN');
  heading.parentElement=new Element('White relief £34.20',{},'DIV');panel.contains=e=>e===heading;
  f.nodes['#panel']=[panel];f.nodes['#heading']=[heading];f.nodes['#marker']=[new Element('',{},'DIV')];f.nodes['#count']=[new Element('1',{},'SPAN')];
  f.context.__boldstoneMedia={job:'one',sha256:'hash',committed:true};f.root.setAttribute('data-boldstone-job','one');
  const tag={name:'White relief',price_text:'£34.20'};
  const request={op:'attest_product_tag',job:'one',mediaSha256:'hash',tag,panel:{selector:'#panel'},heading:{selector:'#heading'},markers:{selector:'#marker'}};
  heading.parentElement.innerText='White relief £44.20';assert.equal(f.run(request).code,'PRODUCT_TAG_SELECTION_MISMATCH');
  heading.parentElement.innerText='White relief £34.20';assert.equal(f.run(request).ok,true);
  const check={locator:{selector:'#count'},text:'1',tag_receipt:tag};
  assert.equal(f.run({op:'assert',job:'one',mediaSha256:'hash',checks:[check]}).ok,true);
  assert.equal(f.run({op:'assert',job:'two',mediaSha256:'hash',checks:[check]}).code,'PRODUCT_TAG_RECEIPT_MISSING');
  f.nodes['#count'][0].innerText='0';assert.equal(f.run({op:'assert',job:'one',mediaSha256:'hash',checks:[check]}).code,'TEXT_READBACK_CHANGED');
});
test('a hidden retained dialog does not block readiness but an open one does', () => {
  const f=fixture(), modal=new Element('Old confirmation',{},'DIV'), wrapper=new Element('',{},'DIV');
  modal.parentElement=wrapper;wrapper.opacity='0';f.nodes['#modal']=[modal];
  const request={op:'assert',checks:[{locator:{selector:'#modal',painted:true},absent:true}]};
  assert.equal(f.run(request).ok,true);wrapper.opacity='1';assert.equal(f.run(request).code,'UNFINISHED_DIALOG');
});

test('an account change before dropping a verified image blocks its file event', async () => {
  const f=fixture(), actor=new Element('Sally Price'), zone=new Element('',{},'DIV');
  f.nodes['#actor']=[actor];f.nodes['#zone']=[zone];
  const bytes=Buffer.from('reviewed original photograph'), sha=createHash('sha256').update(bytes).digest('hex');
  const common={job:'drop-job',mediaSha256:sha,checks:[{locator:{selector:'#actor',name:'Sally Price'}}]};
  assert.equal(f.run({op:'upload_begin',locator:{selector:'#zone'},method:'drop',name:'photo.png',type:'image/png',size:bytes.length,...common}).ok,true);
  f.run({op:'upload_chunk',index:0,data:bytes.toString('base64'),...common});
  f.run({op:'upload_finish',chunks:1,...common});
  for(let i=0;i<30 && f.context.__boldstoneMedia.status==='HASHING';i++)await new Promise(resolve=>setTimeout(resolve,2));
  assert.equal(f.run({op:'upload_commit',...common}).status,'DRAG_ENTERED');
  f.run({op:'upload_drop',phase:'over',...common});actor.innerText='Different account';
  assert.equal(f.run({op:'upload_drop',phase:'drop',...common}).code,'CONTROL_MISSING');
  assert.deepEqual(zone.events,['dragenter','dragover']);
});
test('the main composer must retain the exact authored photo alt text', () => {
  const f=fixture(), photo=new Element('',{alt:'Wrong image description'},'IMG');f.nodes['#photo']=[photo];
  const check={locator:{selector:'#photo'},image:true,alt_text:'Reviewed description'};
  assert.equal(f.run({op:'assert',checks:[check]}).code,'PHOTO_ALT_TEXT_CHANGED');
  photo.setAttribute('alt','Reviewed description');assert.equal(f.run({op:'assert',checks:[check]}).ok,true);
});

test('a scoped success link can identify the native post outside alert roles', () => {
  const f=fixture(), link=new Element('View post',{},'A');link.href='https://www.linkedin.com/feed/update/urn:li:activity:123456/';
  f.nodes['a[href]']=[link];
  const request={op:'discover',pattern:'^https://www\\.linkedin\\.com/feed/update/urn:li:activity:[0-9]+/$',roots:[{selector:'a[href]',name:'View post'}]};
  assert.equal(f.run(request).url,link.href);
  const other=new Element('View post',{},'A');other.href='https://www.linkedin.com/feed/update/urn:li:activity:789/';f.nodes['a[href]'].push(other);
  assert.equal(f.run(request).code,'AMBIGUOUS_NATIVE_POST');
});
