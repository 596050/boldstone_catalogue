const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const tag=fs.readFileSync(path.join(__dirname,'pinterest_tag.js'),'utf8').replace('__BOLDSTONE_PINTEREST_CONFIG__',JSON.stringify({tagId:'2612823030261',products:{TEST:{id:'variant-1',path:'/buy/p/test'}}}));
const funnel=fs.readFileSync(process.argv[2]||path.join(__dirname,'shopping_funnel.js'),'utf8');
function setup(performance='rejected',marketing='rejected',pathname='/buy/p/test',productName='Test sculpture — boldstone'){
  const choices={performance,marketing},requests=[],ga=[],timers=[],events={},winEvents={};let count=0,observer;
  const button={disabled:false,isConnected:true,classList:{contains:()=>false}};
  const product={textContent:JSON.stringify({'@type':'Product',name:productName,offers:{'@type':'Offer',sku:'TEST',price:'40.20',priceCurrency:'GBP',url:'https://boldstonesculpture.com/buy/p/test'}})};
  const document={readyState:'complete',body:{},head:{appendChild:s=>requests.push(s.src)},
    createElement:()=>({}),addEventListener:(k,fn)=>events[k]=fn,
    querySelector:selector=>selector==='.sqs-add-to-cart-button'?button:null,
    querySelectorAll:selector=>selector==='script[type="application/ld+json"]'?[product]:selector==='.sqs-cart-initialized .sqs-cart-quantity'?[{textContent:String(count)}]:[]};
  const window={getSquarespaceCookies:()=>choices,gtag:(...a)=>ga.push(a),addEventListener:(k,fn)=>winEvents[k]=fn};
  const context={window,document,location:{pathname,href:'https://boldstonesculpture.com'+pathname},URL,Date,console,setTimeout:fn=>timers.push(fn),MutationObserver:class{constructor(fn){observer=fn;}observe(){}}};
  vm.createContext(context);vm.runInContext(tag,context);vm.runInContext(funnel,context);
  return {window,choices,requests,ga,events,queue:()=>window.pintrk?.queue||[],tracks:()=> (window.pintrk?.queue||[]).filter(q=>q[0]==='track'),flush:()=>{while(timers.length)timers.shift()();},change:(p,m)=>{choices.performance=p;choices.marketing=m;window.onCookieBannerInteraction();while(timers.length)timers.shift()();},
    click:(trusted=true)=>events.click({isTrusted:trusted,target:{closest:selector=>selector==='.sqs-add-to-cart-button'?button:null}}),increase:()=>{count++;observer();while(timers.length)timers.shift()();}};
}
let checks=0;function test(name,fn){fn();checks++;console.log('PASS '+name);}
test('No consent makes no Pinterest request and no analytics event',()=>{const s=setup();assert.equal(s.requests.length,0);assert.equal(s.ga.length,0);assert.equal(s.tracks().length,0);});
test('Performance only permits GA4 but never Pinterest',()=>{const s=setup('accepted');assert.equal(s.ga.length,1);assert.equal(s.requests.length,0);});
test('Marketing only permits matched Pinterest product view but never GA4',()=>{const s=setup('rejected','accepted');assert.equal(s.ga.length,0);assert.equal(s.requests.length,1);const q=s.tracks();assert.equal(q.length,1);assert.equal(q[0][1],'pagevisit');assert.equal(q[0][2].line_items[0].product_id,'variant-1');assert.equal(q[0][2].currency,'GBP');assert.equal(q[0][2].value,40.20);});
test('Both choices keep each platform to one product view',()=>{const s=setup('accepted','accepted');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,1);});
test('Late consent starts once and a repeat callback cannot duplicate views',()=>{const s=setup();s.change('accepted','accepted');s.change('accepted','accepted');assert.equal(s.requests.length,1);assert.equal(s.tracks().length,1);assert.equal(s.ga.length,1);});
test('Withdrawal invokes Pinterest consent revocation and stops later actions',()=>{const s=setup('accepted','accepted');s.change('rejected','rejected');assert(s.queue().some(q=>q[0]==='setconsent'&&q[1]===false));s.click();s.increase();assert.equal(s.tracks().length,1);});
test('Reaccepting does not load a second SDK or duplicate the view',()=>{const s=setup('accepted','accepted');s.change('rejected','rejected');s.change('accepted','accepted');assert.equal(s.requests.length,1);assert.equal(s.tracks().length,1);});
test('Untrusted clicks cannot generate an add-to-cart event',()=>{const s=setup('accepted','accepted');s.click(false);s.increase();assert.equal(s.tracks().length,1);});
test('A click without a confirmed cart increase cannot generate an addition',()=>{const s=setup('accepted','accepted');s.click();s.flush();assert.equal(s.tracks().length,1);});
test('A trusted click plus settled quantity increase sends the exact matched item',()=>{const s=setup('accepted','accepted');s.click();s.increase();const q=s.tracks().filter(q=>q[1]==='addtocart');assert.equal(q.length,1);assert.equal(q[0][2].line_items[0].product_id,'variant-1');assert.equal(q[0][2].order_quantity,1);assert.equal(q[0][2].value,40.20);assert.equal(s.ga.filter(q=>q[1]==='add_to_cart').length,1);});
test('Unknown or mixed-cart identities fail rather than claiming a match',()=>{const s=setup('accepted','accepted');assert.equal(s.window.BoldstonePinterest.commerce('add_to_cart',[{item_id:'UNKNOWN',price:10,quantity:1}], 'GBP'),false);assert.equal(s.tracks().length,1);});
test('Invalid currency, price or quantity cannot create a commerce event',()=>{const s=setup('accepted','accepted');for(const [price,quantity,currency] of [[10,1,'USD'],[NaN,1,'GBP'],[10,0,'GBP'],[10,1.5,'GBP']])assert.equal(s.window.BoldstonePinterest.commerce('add_to_cart',[{item_id:'TEST',price,quantity}],currency),false);assert.equal(s.tracks().length,1);});
test('Starting checkout is distinct from completing a purchase',()=>{const s=setup('accepted','accepted');const items=[{item_id:'TEST',item_name:'Test sculpture',price:40.2,quantity:1}];assert.equal(s.window.BoldstonePinterest.commerce('begin_checkout',items,'GBP'),true);assert.equal(s.tracks().at(-1)[1],'initiatecheckout');assert.equal(s.window.BoldstonePinterest.commerce('purchase',items,'GBP'),false);assert(!s.tracks().some(q=>q[1]==='checkout'));});
test('Generic pages send one page visit and no made-up line items',()=>{const s=setup('rejected','accepted','/');assert.equal(s.tracks().length,1);assert.equal(s.tracks()[0][1],'pagevisit');assert(!s.tracks()[0][2].line_items);});
test('No email, unconsented noscript pixel or customer fields are added',()=>{assert(!/customerEmailAddress|hashed_email|<noscript>|pd\[em\]|\{\s*em\s*:/.test(tag));});
test('Granting marketing after an analytics-only view delivers the matched Pinterest view once',()=>{const s=setup('accepted','rejected');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,0);s.change('accepted','accepted');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,1);assert.equal(s.tracks()[0][1],'pagevisit');assert.equal(s.tracks()[0][2].line_items[0].product_id,'variant-1');s.change('accepted','accepted');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,1);});
test('Granting analytics after a marketing-only view delivers GA4 once without duplicating Pinterest',()=>{const s=setup('rejected','accepted');assert.equal(s.ga.length,0);assert.equal(s.tracks().length,1);s.change('accepted','accepted');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,1);s.change('accepted','accepted');assert.equal(s.ga.length,1);assert.equal(s.tracks().length,1);});
test('Object prototype names cannot impersonate reviewed merchant SKUs',()=>{
  const s=setup('accepted','accepted');
  for(const item_id of ['toString','constructor','__proto__'])assert.equal(s.window.BoldstonePinterest.commerce('add_to_cart',[{item_id,item_name:'Unknown',price:10,quantity:1}],'GBP'),false);
  assert.equal(s.tracks().length,1);
});
test('A known SKU cannot claim a product view on another product path',()=>{
  const s=setup('accepted','accepted','/buy/p/other');const before=s.tracks().length;
  assert.equal(s.window.BoldstonePinterest.commerce('view_item',[{item_id:'TEST',item_name:'Test',price:10,quantity:1}],'GBP'),false);
  assert.equal(s.tracks().length,before);
});
test('Malformed product names do not become literal null or empty analytics items',()=>{
  for(const name of [null,'','   ']){
    const s=setup('accepted','accepted','/buy/p/test',name);
    assert.equal(s.ga.length,0);assert.equal(s.tracks().length,0);
  }
});
test('An external checkout-looking link cannot count as the store checkout',()=>{
  const ga=[],events={};
  const source={storeCurrency:'GBP',cart:{items:[{productUrl:'/buy/p/test',sku:'TEST',productName:'Test sculpture',unitPrice:{decimalValue:'40.20',currencyCode:'GBP'}}]}};
  const row={querySelector:s=>s==='.cart-row-title'?{href:'https://boldstonesculpture.com/buy/p/test'}:s==='.cart-row-qty-input'?{value:'1'}:s==='.cart-row-price'?{textContent:'£40.20'}:null};
  const document={readyState:'complete',body:{},addEventListener:(k,fn)=>events[k]=fn,
    querySelector:s=>s==='#sqs-cart-root > script[type="application/json"]'?{textContent:JSON.stringify(source)}:null,
    querySelectorAll:s=>s==='[data-testid="cart-table-row"]'?[row]:[]};
  const window={getSquarespaceCookies:()=>({performance:'accepted',marketing:'rejected'}),gtag:(...args)=>ga.push(args),addEventListener:()=>{}};
  const context={window,document,location:{pathname:'/cart',href:'https://boldstonesculpture.com/cart'},URL,Date,console,setTimeout:()=>{},MutationObserver:class{observe(){}}};
  vm.createContext(context);vm.runInContext(funnel,context);
  const click=href=>events.click({isTrusted:true,target:{closest:s=>s==='a.cart-checkout-button[href]'?{href}:null}});
  click('https://example.com/commerce/goto-checkout');
  assert.equal(ga.filter(call=>call[1]==='begin_checkout').length,0);
  click('https://boldstonesculpture.com/commerce/goto-checkout');
  assert.equal(ga.filter(call=>call[1]==='begin_checkout').length,1);
});
console.log(checks+' tracking checks passed');
