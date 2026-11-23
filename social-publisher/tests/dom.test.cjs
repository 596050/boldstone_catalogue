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
  constructor(type) { super('', { type }, 'INPUT'); this._value = ''; this.validity={valid:true}; }
  get value() { return this._value; }
  set value(v) { this._value = v; }
  select() {this.selected=true;}
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
test('viewport scoping excludes an offscreen duplicate without choosing an arbitrary match',()=>{
 const f=fixture(),shown=new Element('More options'),offscreen=new Element('More options');f.context.window={innerWidth:1000,innerHeight:800};
 shown.getBoundingClientRect=()=>({left:10,top:20,right:110,bottom:100,width:100,height:80});
 offscreen.getBoundingClientRect=()=>({left:10,top:900,right:110,bottom:980,width:100,height:80});
 f.nodes.button=[shown,offscreen];const result=f.run({op:'click',locator:[{selector:'button',name:'More options',in_view:true}]});
 assert.equal(result.ok,true);assert.equal(shown.clicked,1);assert.equal(offscreen.clicked,0);
});
test('history readers reject a different profile and a post without the owned author', () => {
  const f=fixture();
  for(const op of ['source_grid','source_modal','scroll_page']) assert.equal(f.run({op}).code,'SOURCE_PROFILE_REQUIRED');
  f.context.location.href='https://www.instagram.com/p/source/';
  const dialog=new Element('',{},'DIV');dialog.nodes.h1=[new Element('Original sculpture caption',{},'H1')];
  f.nodes['[role=dialog]']=[dialog];
  assert.equal(f.run({op:'source_modal'}).code,'SOURCE_AUTHOR_OR_CAPTION_MISSING');
});
test('the history modal reader keeps the owned caption and excludes recommendation photos', () => {
  const f=fixture();f.context.location.href='https://www.instagram.com/p/source/';
  const dialog=new Element('',{},'DIV'),author=new Element('boldstonesculpture',{},'A');author.href='https://www.instagram.com/boldstonesculpture/';
  const photo=new Element('',{},'IMG');photo.src='https://scontent.cdninstagram.com/original.jpg';photo.alt='Original relief';
  dialog.nodes.h1=[new Element('Original sculpture caption',{},'H1')];dialog.nodes['h2 a[href]']=[author];dialog.nodes.img=[photo];
  f.nodes['[role=dialog]']=[dialog];f.nodes.img=[new Element('Unrelated recommendation',{},'IMG')];
  const result=f.run({op:'source_modal'});
  assert.equal(result.caption,'Original sculpture caption');assert.equal(result.photos.length,1);assert.equal(result.photos[0].src,photo.src);assert.equal(result.author,'boldstonesculpture');
});
test('an owned post without a caption remains readable through its native author header',()=>{
  const f=fixture();f.context.location.href='https://www.instagram.com/p/source/?img_index=1';
  const dialog=new Element('',{},'DIV'),author=new Element('boldstonesculpture',{},'A');author.href='https://www.instagram.com/boldstonesculpture/';
  dialog.nodes['header a[href]']=[author];f.nodes['[role=dialog]']=[dialog];
  const result=f.run({op:'source_modal'});assert.equal(result.ok,true);assert.equal(result.caption,'');assert.equal(result.author,'boldstonesculpture');
});
test('generic operations cannot click Publish, Post or Share', () => {
  for (const name of ['Publish', 'Post', 'Share', 'Publish post', 'Schedule now', 'Create ad', 'Boost', 'Promote']) {
    const f = fixture(), button = new Element(name); f.nodes['button'] = [button];
    assert.equal(f.run({ op: 'click', locator: { selector: 'button' } }).code, 'GUARDED_ACTION_REQUIRED');
    assert.equal(button.clicked, 0);
  }
});
test('published Meta platform submenu is navigation, while other post buttons remain guarded',()=>{
 const f=fixture();Object.assign(f.context.location,{hostname:'business.facebook.com',pathname:'/latest/posts/published_posts/'});
 const menu=new Element('Facebook post\nInstagram post',{role:'menu'}),button=new Element('Facebook post',{role:'button'});button.parent=menu;f.nodes.button=[button];
 assert.equal(f.run({op:'click',locator:{selector:'button'}}).ok,true);assert.equal(button.clicked,1);
 menu.innerText='Facebook post Publish';assert.equal(f.run({op:'click',locator:{selector:'button'}}).code,'GUARDED_ACTION_REQUIRED');
 menu.innerText='Facebook post Instagram post';f.context.location.pathname='/latest/composer/';
 assert.equal(f.run({op:'click',locator:{selector:'button'}}).code,'GUARDED_ACTION_REQUIRED');assert.equal(button.clicked,1);
});
test('Google native videos require loaded metadata, exact duration and aspect ratio',()=>{
 const f=fixture();Object.assign(f.context.location,{href:'https://www.google.com/local/business/123/promote/updates/add',pathname:'/local/business/123/promote/updates/add'});
 const v=new Element('',{},'VIDEO');Object.assign(v,{src:'blob:https://www.google.com/native-upload',videoWidth:720,videoHeight:1280,duration:3.033333,readyState:4});f.nodes.video=[v];
 const request={op:'assert',job:'clip',mediaSha256:'a'.repeat(64),checks:[{locator:{selector:'video'},video:true,duration:3.033333,width:720,height:1280}]};
 assert.equal(f.run(request).checks[0].video.media_type,'video/mp4');
 v.readyState=1;assert.equal(f.run(request).code,'VIDEO_NOT_LOADED');v.readyState=4;
 v.duration=10;assert.equal(f.run(request).code,'NATIVE_VIDEO_MISMATCH');v.duration=3.033333;
 v.videoWidth=1280;assert.equal(f.run(request).code,'NATIVE_VIDEO_MISMATCH');v.videoWidth=720;
 v.src='https://unrelated.example/video.mp4';assert.equal(f.run(request).code,'VIDEO_SOURCE_INVALID');
});
test('a photograph cannot satisfy a Google video guard',()=>{
 const f=fixture();f.context.location.href='https://www.google.com/local/business/123/promote/updates/456/edit';
 f.nodes.media=[new Element('',{},'IMG')];
 assert.equal(f.run({op:'assert',job:'clip',mediaSha256:'a'.repeat(64),checks:[{locator:{selector:'media'},video:true,duration:3,width:720,height:1280}]}).code,'VIDEO_CONTEXT_REQUIRED');
});
test('video readiness is checked in the one allowed Post turn and a retry cannot post again',()=>{
 const f=fixture();Object.assign(f.context.location,{href:'https://www.google.com/local/business/123/promote/updates/add',pathname:'/local/business/123/promote/updates/add'});
 const video=new Element('',{},'VIDEO'),post=new Element('Post');Object.assign(video,{src:'blob:https://www.google.com/clip',readyState:1,videoWidth:720,videoHeight:720,duration:10});f.nodes.video=[video];f.nodes.post=[post];
 f.context.__boldstoneMedia={job:'clip',sha256:'a'.repeat(64),committed:true};
 const request={op:'submit',job:'clip',mediaSha256:'a'.repeat(64),checks:[{locator:{selector:'video'},video:true,duration:10,width:720,height:720}],submit:{selector:'post'}};
 assert.equal(f.run(request).code,'VIDEO_NOT_LOADED');assert.equal(post.clicked,0);
 video.readyState=4;assert.equal(f.run(request).ok,true);assert.equal(post.clicked,1);
 assert.equal(f.run(request).code,'SUBMIT_ALREADY_CLICKED');assert.equal(post.clicked,1);
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
function googleCorrectionFixture() {
  const f=fixture(),post=new Element('Post'),input=new Input('url');input.value='https://boldstonesculpture.com/buy/p/one';
  f.context.location.href='https://www.google.com/local/business/123/promote/updates/add';
  f.root.setAttribute('data-boldstone-job','one');f.root.setAttribute('data-boldstone-submission-one','attempted');
  f.context.__boldstoneMedia={job:'one',sha256:'hash',committed:true};
  f.nodes['#post']=[post];f.nodes['input[type="url"][aria-invalid="false"]']=[input];
  return {f,post,request:{op:'submit_google_validation_correction',job:'one',mediaSha256:'hash',
    submit:[{selector:'#post'}],checks:[],purchaseURL:input.value,rejectionEvidenceSha256:'a'.repeat(64)}};
}
test('a proven Google validation correction has its own durable page marker and cannot replay',()=>{
  const {f,post,request}=googleCorrectionFixture();
  assert.equal(f.run(request).status,'CLICKED_UNCONFIRMED');assert.equal(post.clicked,1);
  assert.equal(f.root.getAttribute('data-boldstone-submission-one'),'attempted');
  assert.equal(f.run(request).code,'SUBMIT_ALREADY_CLICKED');assert.equal(post.clicked,1);
});
test('Google URL entry can use Chrome native insertText without changing other fields',()=>{
  const f=fixture(),input=new Input('url');f.nodes.input=[input];
  f.context.location.href='https://www.google.com/local/business/123/promote/updates/add';
  f.context.document.execCommand=(command,unused,value)=>{assert.equal(command,'insertText');assert.equal(input.focused,true);assert.equal(input.selected,true);input.value=value;return true;};
  const url='https://boldstonesculpture.com/buy/p/one';
  assert.equal(f.run({op:'set_text',locator:{selector:'input'},value:url,method:'insert_text'}).ok,true);
  assert.equal(input.value,url);
  f.context.location.href='https://example.com/';input.value='';
  assert.equal(f.run({op:'set_text',locator:{selector:'input'},value:url,method:'insert_text'}).code,'NATIVE_URL_EDITOR_REQUIRED');
});
test('native field guards accept an untouched valid URL and reject browser or Google errors',()=>{
  const f=fixture(),input=new Input('url');input.value='https://boldstonesculpture.com/buy/p/one';f.nodes.input=[input];
  const request={op:'assert',checks:[{locator:{selector:'input'},text:input.value,valid:true}]};
  assert.equal(f.run(request).checks[0].valid,true);
  input.attrs['aria-invalid']='true';assert.equal(f.run(request).code,'NATIVE_FIELD_INVALID');
  input.attrs['aria-invalid']='false';input.validity.valid=false;assert.equal(f.run(request).code,'NATIVE_FIELD_INVALID');
});
test('Google validation correction requires the original owned job, submission and evidence hash',()=>{
  for(const change of [x=>x.f.root.setAttribute('data-boldstone-job','other'),x=>x.f.root.setAttribute('data-boldstone-submission-one',''),
      x=>x.request.rejectionEvidenceSha256='',x=>x.f.context.location.href='https://www.linkedin.com/sharing/compose']){
    const x=googleCorrectionFixture();change(x);
    assert.equal(x.f.run(x.request).code,'GOOGLE_VALIDATION_CORRECTION_CONTEXT_MISSING');assert.equal(x.post.clicked,0);
  }
});
test('a validation correction still requires the exact Google-validated product URL',()=>{
  const x=googleCorrectionFixture();x.request.purchaseURL='https://example.com/';
  assert.equal(x.f.run(x.request).code,'GOOGLE_LINK_NOT_VALIDATED');assert.equal(x.post.clicked,0);
  const y=googleCorrectionFixture();y.f.nodes['input[type="url"][aria-invalid="false"]']=[];
  assert.equal(y.f.run(y.request).code,'CONTROL_MISSING');assert.equal(y.post.clicked,0);
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

function rejectedRevisionFixture() {
  const f=fixture();f.context.location.href='https://www.google.com/local/business/123/promote/updates/456/edit';f.context.location.pathname='/local/business/123/promote/updates/456/edit';
  const caption=new Textarea('Revised sculpture caption'),photo=new Element('',{href:'blob:https://www.google.com/same-photo'},'image');photo.localName='image';photo.namespaceURI='http://www.w3.org/2000/svg';
  const button=new Element('Post'),url=new Input('url'),schedule=new Input('checkbox'),heading=new Element('Edit update');url.value='https://boldstonesculpture.com/';
  Object.assign(f.nodes,{'h1':[heading],'#account':[new Element('Boldstone')],'textarea[maxlength="1500"]':[caption],'#photo':[photo],'#url':[url],'#schedule':[schedule],'footer button':[button]});
  f.context.Image=class {set src(value){this.naturalWidth=1000;this.naturalHeight=1000;this.onload();}};
  const request={op:'submit_google_rejected_revision',nativeURL:f.context.location.href,job:'one',mediaSha256:'a'.repeat(64),rejectionEvidenceSha256:'b'.repeat(64),originalCaption:'Original sculpture caption',revisedCaption:caption.value,
    checks:[{purpose:'account',url_path_prefix:'/local/business/123/',locator:{selector:'#account'},text:'Boldstone'},{purpose:'caption',locator:{selector:'textarea[maxlength="1500"]'},text:caption.value},{purpose:'photo',locator:{selector:'#photo'},image:true,svg_image:true},{purpose:'purchase',locator:{selector:'#url'},text:url.value,valid:true},{purpose:'schedule',locator:{selector:'#schedule'},checked:false}]};
  f.run({op:'probe_svg_photo',locator:{selector:'#photo'},job:'one',mediaSha256:'a'.repeat(64)});
  return {f,request,button,caption};
}
test('existing rejected Google record revision clicks once and cannot create a replacement post',()=>{
  const {f,request,button}=rejectedRevisionFixture();assert.equal(f.run(request).status,'EXISTING_REJECTED_POST_REVISION_CLICKED');assert.equal(button.clicked,1);
  assert.equal(f.run(request).code,'SUBMIT_ALREADY_CLICKED');assert.equal(button.clicked,1);
  f.context.location.href='https://www.google.com/local/business/123/promote/updates/add';assert.equal(f.run({...request,nativeURL:f.context.location.href}).code,'GOOGLE_REJECTED_REVISION_CONTEXT_REQUIRED');assert.equal(button.clicked,1);
});
test('rejected record revision requires exact saved record, original photograph and all guards',()=>{
  for(const change of [r=>({...r,nativeURL:r.nativeURL.replace('/456/','/789/')}),r=>({...r,rejectionEvidenceSha256:''}),r=>({...r,originalCaption:r.revisedCaption}),r=>({...r,checks:r.checks.filter(c=>c.purpose!=='schedule')}),r=>({...r,mediaSha256:'c'.repeat(64)})]){
    const {f,request,button}=rejectedRevisionFixture();assert.equal(f.run(change(request)).ok,false);assert.equal(button.clicked,0);
  }
  const {f,request,button,caption}=rejectedRevisionFixture();caption.value='User edited this';assert.equal(f.run(request).code,'TEXT_READBACK_CHANGED');assert.equal(button.clicked,0);
});
test('Google inventory probes expose distinct rendered native record identities for pagination',()=>{
 const f=fixture();f.context.window={scrollY:0,innerHeight:800};f.document.scrollingElement={scrollHeight:1200};
 const one=new Element('',{'data-post-name':'accounts/-/locations/123/localPosts/456'}),duplicate=new Element('',{'data-post-name':'accounts/-/locations/123/localPosts/456'}),two=new Element('',{'data-post-name':'accounts/-/locations/123/localPosts/789'}),invalid=new Element('',{'data-post-name':'unrelated'});
 f.nodes['div[data-post-name]']=[one,duplicate,two,invalid];const result=f.run({op:'probe'});assert.equal(result.ok,true);assert.deepEqual(result.googlePostRecordNames,['accounts/-/locations/123/localPosts/456','accounts/-/locations/123/localPosts/789']);
});
test('same-document upload status distinguishes an unclicked intent from an attempted submission',()=>{
 const f=fixture();f.context.__boldstoneMedia={job:'one',sha256:'hash',committed:true,status:'HASH_VERIFIED'};f.root.setAttribute('data-boldstone-job','one');f.nodes['#post']=[new Element('Post')];
 const before=f.run({op:'upload_status',job:'one'});assert.equal(before.same_job,true);assert.equal(before.document_job,'one');assert.equal(before.submission_marker,null);
 assert.equal(f.run({op:'submit',job:'one',mediaSha256:'hash',checks:[],submit:{selector:'#post'}}).ok,true);
 assert.equal(f.run({op:'upload_status',job:'one'}).submission_marker,'attempted');assert.equal(f.run({op:'upload_status',job:'other'}).same_job,false);
});

test('accessible locators exclude a closed Threads alt editor retained during background animation',()=>{
 const f=fixture(),main=new Element('Done'),closed=new Element('Done');
 main.closest=()=>null;closed.closest=()=>new Element('',{'aria-hidden':'true'});
 f.nodes['[role=button]']=[main,closed];
 const r=f.run({op:'click',locator:[{selector:'[role=button]',name:'Done',accessible:true}]});
 assert.equal(r.ok,true);assert.equal(main.clicked,1);assert.equal(closed.clicked,0);
});
test('Threads reconciliation finds only a full caption and native time link in the same post',()=>{
 const f=fixture();f.context.location.href='https://www.threads.com/@boldstonesculpture';
 f.context.location.hostname='www.threads.com';f.context.location.origin='https://www.threads.com';
 f.context.location.pathname='/@boldstonesculpture';
 const caption=new Element('Sculpture A\nA complete caption.'),root=new Element('');
 const link=new Element('Just now',{},'A');link.href='https://www.threads.com/@boldstonesculpture/post/Native123';
 link.nodes.time=[new Element('')];root.nodes['a[href]']=[link];caption.parentElement=root;
 f.nodes['div.x1a6qonq']=[caption];
 const request={op:'find_threads_post',username:'boldstonesculpture',caption:'Sculpture A\nA complete caption.'};
 assert.equal(f.run(request).url,link.href);
 assert.equal(f.run({...request,username:'anotherprofile'}).code,'WRONG_THREADS_PROFILE');
 f.nodes['div.x1a6qonq']=[caption,new Element(caption.innerText)];
 assert.equal(f.run(request).code,'AMBIGUOUS_NATIVE_CAPTION');
 f.nodes['div.x1a6qonq']=[caption];root.nodes['a[href]']=[];
 assert.equal(f.run(request).url,null);
 assert.equal(link.clicked,0);
});
