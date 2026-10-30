const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const listeners={},node={addEventListener(){},querySelectorAll:()=>[]};
  const context=vm.createContext({console,URL,URLSearchParams,document:{createElement:()=>({}),querySelector:()=>node,querySelectorAll:()=>[],addEventListener:(type,fn)=>{listeners[type]=fn;}},
    window:{addEventListener(){}},location:{hash:''},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  run(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  return {run,context,listeners};
}
test('a Dropbox photo without a retained local image gets on-demand URLs',()=>{
  const h=harness();h.run("var photo={id:'id:known',source:'Dropbox',local_preview:false,original:{dropbox_content_hash:'abc',bytes:1234}};");
  assert.equal(h.run('imageURL(photo)'),'/api/image?id=id%3Aknown&v=abc&size=thumb');
  assert.equal(h.run('imageURL(photo,true)'),'/api/image?id=id%3Aknown&v=abc');
});
test('platform CDN fallback and unknown original qualifications are preserved',()=>{
  const h=harness();
  assert.equal(h.run("imageURL({source:'Shopify',remote_preview:'https://cdn.shopify.com/photo.jpg'})"),'https://cdn.shopify.com/photo.jpg');
  assert.equal(h.run("imageURL({source:'Dropbox',id:'id:unknown',original:{}})"),undefined);
});
test('full image failure falls back once without moving cards or changing reviews',()=>{
  const h=harness(),src='/api/image?id=id%3Atest&v=abc',image={tagName:'IMG',dataset:{},getAttribute:()=>src,replaceWith(node){this.replaced=node;}};
  h.listeners.error({target:image});assert.equal(image.src,src+'&size=thumb');assert.match(image.title,/Thumbnail/);
  image.src='unchanged';h.listeners.error({target:image});assert.equal(image.src,'unchanged');assert.match(image.replaced.textContent,/unavailable/);
  const thumb={tagName:'IMG',dataset:{},getAttribute:()=>src+'&size=thumb',replaceWith(node){this.replaced=node;}};
  h.listeners.error({target:thumb});assert.equal(thumb.src,undefined);assert.match(thumb.replaced.textContent,/unavailable/);
});
