const {JSDOM} = require('/tmp/boldstone-funnel-tests-20261031/node_modules/jsdom');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname,'ecommerce-tracking.js'),'utf8');
const productHTML = fs.readFileSync(path.join(__dirname,'BSI-67EA9E9D261A-public.html'),'utf8');
let passed=[];
const wait = () => new Promise(r=>setTimeout(r,160));
async function fixture(html=productHTML, route='/buy/p/moonshell-lava-1-white', allowed=true) {
  const d=new JSDOM(html,{url:'https://boldstonesculpture.com'+route,runScripts:'outside-only'}), w=d.window;
  let events=[], handlers=[], allow=allowed, now=1_000_000;
  const add=w.document.addEventListener.bind(w.document);
  w.document.addEventListener=(name,cb,...args)=>{if(name==='click') handlers.push(cb);add(name,cb,...args)};
  w.getSquarespaceCookies=()=>({performance:allow?'accepted':'declined'});
  w.gtag=(...v)=>events.push(JSON.parse(JSON.stringify(v)));
  w.Date.now=()=>now;
  w.document.querySelectorAll('a[href="/cart"]').forEach(el=>el.classList.add('sqs-cart-initialized'));
  w.document.querySelectorAll('.sqs-cart-quantity').forEach(el=>el.textContent='0');
  await wait();w.eval(code);await wait();
  return {w,events,close:()=>w.close(),setConsent:v=>allow=v,advance:v=>now+=v,
    click:(selector,trusted=true)=>handlers.forEach(h=>h({target:w.document.querySelector(selector),isTrusted:trusted})),
    quantity:n=>w.document.querySelectorAll('.sqs-cart-quantity').forEach(el=>el.textContent=String(n))};
}
async function test(name,fn){await fn();passed.push(name);console.log('PASS',name)}
const cartHTML=(quantity=1,price='87.60',duplicate=false)=>{
 const item={sku:'BOLD-67EA9E9D261A',productName:'Lava Moonshell I - White',productUrl:'/buy/p/moonshell-lava-1-white',unitPrice:{currencyCode:'GBP',decimalValue:price}};
 const data={storeCurrency:'GBP',cart:{cartToken:'MUST-NOT-LEAK',shippingLocation:{line1:'PRIVATE'},items:duplicate?[item,{...item,sku:'OTHER'}]:[item]}};
 return `<div id="sqs-cart-root"><script type="application/json">${JSON.stringify(data)}</script><div data-testid="cart-table-row"><a class="cart-row-title" href="${item.productUrl}">Product</a><input class="cart-row-qty-input" value="${quantity}"><p class="cart-row-price">£${(quantity*Number(price)).toFixed(2)}</p></div><a class="cart-checkout-button" href="/commerce/goto-checkout">Checkout</a></div>`;
};
(async()=>{
 await test('live product markup maps the current SKU and price once',async()=>{let f=await fixture();assert.equal(f.events.length,1);assert.equal(f.events[0][1],'view_item');assert.equal(f.events[0][2].items[0].item_id,'BOLD-67EA9E9D261A');assert.equal(f.events[0][2].value,87.6);f.w.document.body.classList.add('other');await wait();assert.equal(f.events.length,1);f.close()});
 await test('no analytics before consent; later consent emits one view',async()=>{let f=await fixture(undefined,undefined,false);assert.equal(f.events.length,0);f.click('.sqs-add-to-cart-button');f.quantity(1);await wait();assert.equal(f.events.length,0);f.setConsent(true);f.w.onCookieBannerInteraction();await wait();assert.equal(f.events.length,1);assert.equal(f.events[0][1],'view_item');f.close()});
 await test('failed cart addition never emits add_to_cart',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');await wait();assert.equal(f.events.filter(e=>e[1]==='add_to_cart').length,0);f.close()});
 await test('confirmed genuine addition emits once despite four mirrored counters',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');f.quantity(1);await wait();f.w.document.body.classList.add('again');await wait();assert.equal(f.events.filter(e=>e[1]==='add_to_cart').length,1);f.close()});
 await test('synthetic click and unrelated count change do not count',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button',false);f.quantity(1);await wait();assert.equal(f.events.length,1);f.close()});
 await test('revocation before confirmation prevents the cart event',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');f.setConsent(false);f.quantity(1);await wait();assert.equal(f.events.length,1);f.close()});
 await test('expired attempt cannot claim a later count change',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');f.advance(31000);f.quantity(1);await wait();assert.equal(f.events.length,1);f.close()});
 await test('new attempt after a timeout can still succeed',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');f.advance(31000);f.click('.sqs-add-to-cart-button');f.quantity(1);await wait();assert.equal(f.events.filter(e=>e[1]==='add_to_cart').length,1);f.close()});
 await test('ambiguous quantity increase fails closed',async()=>{let f=await fixture();f.click('.sqs-add-to-cart-button');f.quantity(2);await wait();assert.equal(f.events.length,1);f.close()});
 await test('duplicate installation does not double count',async()=>{let f=await fixture();f.w.eval(code);f.click('.sqs-add-to-cart-button');f.quantity(1);await wait();assert.equal(f.events.length,2);f.close()});
 await test('initial pageshow does not duplicate the initial product view',async()=>{let f=await fixture();f.w.dispatchEvent(new f.w.PageTransitionEvent('pageshow',{persisted:false}));await wait();assert.equal(f.events.length,1);f.close()});
 await test('return from back-forward cache records one fresh view',async()=>{let f=await fixture();f.w.dispatchEvent(new f.w.PageTransitionEvent('pageshow',{persisted:true}));await wait();assert.equal(f.events.length,2);f.w.document.body.classList.add('redraw');await wait();assert.equal(f.events.length,2);f.close()});
 await test('cart totals use current quantity without leaking customer fields',async()=>{let f=await fixture(cartHTML(2),'/cart');assert.equal(f.events[0][1],'view_cart');assert.equal(f.events[0][2].value,175.2);f.click('.cart-checkout-button');f.click('.cart-checkout-button');assert.equal(f.events.filter(e=>e[1]==='begin_checkout').length,1);assert(!JSON.stringify(f.events).includes('PRIVATE'));assert(!JSON.stringify(f.events).includes('MUST-NOT-LEAK'));assert(!f.events.some(e=>e[1]==='purchase'));f.close()});
 await test('multi-variant cart ambiguity is not assigned an incorrect SKU',async()=>{let f=await fixture(cartHTML(1,'87.60',true),'/cart');f.click('.cart-checkout-button');assert.equal(f.events.length,0);f.close()});
 await test('no checkout event without consent',async()=>{let f=await fixture(cartHTML(),'/cart',false);f.click('.cart-checkout-button');assert.equal(f.events.length,0);f.close()});
 await test('initial pageshow does not duplicate the basket view',async()=>{let f=await fixture(cartHTML(),'/cart');f.w.dispatchEvent(new f.w.PageTransitionEvent('pageshow',{persisted:false}));await wait();assert.equal(f.events.length,1);f.close()});
 await test('unsettled quantity and total do not emit checkout',async()=>{let f=await fixture(cartHTML(),'/cart');f.w.document.querySelector('input').value='3';f.click('.cart-checkout-button');assert.equal(f.events.length,1);f.close()});
 fs.writeFileSync(path.join(__dirname,'ecommerce-test-results.json'),JSON.stringify({status:'PASS',tests:passed.length,passed,scope:'Offline DOM fixtures; live receipt verified separately'},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
