// Native UI actions only. Every action is derived from a fresh visible AX state.
export function assertPrimaryPhotoDimensions(photo){
 const width=Number(photo?.width),height=Number(photo?.height);
 if(!Number.isInteger(width)||!Number.isInteger(height)||width<1500||height<1200)
  throw Error('Saatchi primary requires at least 1500 pixels wide and 1200 pixels high in its actual orientation; do not upscale, pad or rotate the artwork to bypass this requirement');
 return {width,height};
}
export function createSaatchiFlow(chrome,fs,h,out){
 let packet=null,intent=null,intentPath=null;
 const esc=x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const address=s=>h.value(s,/text field .*Address and search bar/)||'';
 const ax=s=>s.split('Selected text:')[0];
 const norm=x=>x.replace(/\s+/g,' ').trim();
 const sameRoute=(s,path)=>new RegExp('^(?:https:\\/\\/)?(?:www\\.)?saatchiart\\.com'+esc(path)+'(?:[?#].*)?$').test(address(s));
 const save=()=>fs.writeFile(intentPath,JSON.stringify(intent,null,2));
 async function focus(){
  let s=await h.state();
  if(!/^(?:https:\/\/)?(?:www\.)?saatchiart\.com\//.test(address(s))){
   if(s.includes('dialogue'))throw Error('Inspect the native dialog before continuing');
   await chrome.click(h.idx(s,/^\s*\d+ Window$/));s=await h.state();
   const lines=s.split('\n').filter(x=>/Saatchi Art/.test(x)&&/ID: makeKeyAndOrderFront:/.test(x));
   if(lines.length!==1)throw Error('Saatchi window is absent or ambiguous');
   await chrome.click(Number(lines[0].trim().match(/^\d+/)[0]));s=await h.state();
  }
  if(!/^(?:https:\/\/)?(?:www\.)?saatchiart\.com\//.test(address(s)))throw Error('Saatchi window has not become active');
  return s;
 }
 async function current(stage){
  let s=await focus();const path=intent.native_artwork_id?'/en-gb/studio/art/'+intent.native_artwork_id+'/'+stage:'/en-gb/studio/upload';
  if(!sameRoute(s,path)||!s.includes(packet.title))throw Error('Exact bound artwork and stage are not active');return s;
 }
 function next(s,label){
  const lines=ax(s).split('\n');const start=lines.findIndex(x=>x.includes('button '+label+', Help:'));
  if(start<0)throw Error('Missing section '+label);
  if(!lines[start].includes('Help: Collapse'))throw Error('Section is not visibly expanded: '+label);
  const line=lines.slice(start+1).find(x=>/\d+ button Next$/.test(x));if(!line)throw Error('Missing Next for '+label);return Number(line.trim().match(/^\d+/)[0]);
 }
 async function expanded(stage,label){let s=await current(stage);for(let n=0;n<2&&!s.includes('button '+label+', Help: Collapse');n++){await chrome.getScreenshot({emit:false});s=await current(stage);}if(!s.includes('button '+label+', Help: Collapse'))throw Error('Section did not visibly expand: '+label);return s;}
 function dimension(s,label){
  const lines=ax(s).split('\n');const start=lines.findIndex(x=>x.includes('text '+label+' ( cm )'));
  if(start<0)throw Error('Missing dimension '+label);
  const line=lines.slice(start+1).find(x=>/\d+ text field \(settable\)/.test(x));if(!line)throw Error('Missing dimension control');return Number(line.trim().match(/^\d+/)[0]);
 }
 function dimensionValue(s,label){const index=dimension(s,label);const line=ax(s).split('\n').find(x=>new RegExp('^\\s*'+index+' ').test(x));const value=line.match(/Value: ([^,]+)/)?.[1]||line.match(/text field \(settable\) ([^,]+)$/)?.[1];return Number(value);}
 function radio(s,question,answer){
  const lines=ax(s).split('\n');const start=lines.findIndex(x=>x.includes('text '+question));if(start<0)throw Error('Missing question '+question);
  let end=lines.findIndex((x,i)=>i>start&&/text (?:Is |Does )/.test(x));if(end<0)end=lines.length;
  const matches=lines.slice(start+1,end).filter(x=>x.includes('radio button '+answer+', Value:'));if(matches.length!==1)throw Error('Ambiguous answer');return Number(matches[0].trim().match(/^\d+/)[0]);
 }
 async function dropdown(s,field,answer){await chrome.click(h.idx(s,new RegExp('text field \\(settable\\) '+esc(field)+'$')));s=await current('description');await chrome.click(h.idx(s,new RegExp('button '+esc(answer)+'$')));return current('description');}
 async function start(p){
  assertPrimaryPhotoDimensions(p.photo);
  const registry=JSON.parse(await fs.readFile('/Users/tprice/Documents/boldstone/outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json','utf8'));
  if(registry.some(x=>x.sku===p.sku)||p.native_artwork_id)throw Error('Already bound; complete existing artwork');
  packet=p;intentPath=out+'/saatchi-upload-'+p.catalogue_id+'.json';
  try{await fs.access(intentPath);throw Error('Existing intent must be reconciled');}catch(e){if(e.code!=='ENOENT')throw e;}
  intent={sku:p.sku,catalogue_id:p.catalogue_id,title:p.title,status:'PREPARING_EXACT_NATIVE_UPLOAD',native_artwork_id:null,photo_path:p.photo.native_upload_path,photo_sha256:p.photo.native_upload_sha256,whole_portfolio_audit:'saatchi-fresh-portfolio-audit.json',packing_model_sha256:p.packing_model_source_sha256,price_target_usd:p.target_artwork_price_usd,packed_weight_estimate_kg:p.native_packed_weight_kg_estimate,started_utc:new Date().toISOString()};await save();
  let s=await focus();await chrome.click(h.idx(s,/text field .*Address and search bar/));await chrome.pressKey('super+a');await chrome.paste('https://www.saatchiart.com/en-gb/studio/upload');s=await h.state();if(address(s)!=='https://www.saatchiart.com/en-gb/studio/upload')throw Error('URL entry changed');await chrome.pressKey('Return');s=await h.state();return {status:'UPLOADER_NAVIGATION_SUBMITTED',sku:p.sku,route:address(s)};
 }
 async function resume(p,path){
  const saved=JSON.parse(await fs.readFile(path,'utf8'));if(saved.sku!==p.sku||saved.catalogue_id!==p.catalogue_id)throw Error('Intent mismatch');packet=p;intent=saved;intentPath=path;return {sku:p.sku,status:intent.status,native_id:intent.native_artwork_id};
 }
 async function photo(){
  if(intent.status!=='PREPARING_EXACT_NATIVE_UPLOAD')throw Error('Photo stage was already attempted');
  assertPrimaryPhotoDimensions(packet.photo);
  let s=await focus();if(!sameRoute(s,'/en-gb/studio/upload'))throw Error('New uploader not active');
  const field=h.idx(s,/text field \(settable\) Enter title$/);await chrome.setValue(field,packet.title);s=await current('image');
  if(h.value(s,/text field.*Placeholder: Enter title/)!==packet.title)throw Error('Title input differs');
  await chrome.click(next(s,'Title'));s=await current('image');await chrome.click(h.idx(s,/button ADD PRIMARY IMAGE$/));s=await current('image');
  await chrome.click(h.idx(s,/text Drag and drop image here or  BROWSE IMAGE$/));s=await h.state();if(!s.includes('Open'))throw Error('Native file chooser did not open');
  await chrome.pressKey('super+shift+g');s=await h.state();await chrome.setValue(h.idx(s,/text field.*ID: PathTextField/),packet.photo.native_upload_path);s=await h.state();
  if(!s.split('\n').find(x=>x.includes('ID: PathTextField'))?.includes(packet.photo.native_upload_path))throw Error('Chooser path differs');await chrome.pressKey('Return');s=await h.state();
  if(!s.includes(packet.photo.native_upload_path.split('/').pop()))throw Error('Exact photo is not selected');await chrome.click(h.idx(s,/button Open, ID: OKButton$/));
  intent.status='PHOTO_SELECTED_NATIVE_UPLOAD_PENDING';await save();s=await h.state();return {status:intent.status,sku:packet.sku,uploading:s.includes('Please wait while your image is uploaded')};
 }
 async function acceptPhoto(){
  assertPrimaryPhotoDimensions(packet.photo);
  if(intent.status!=='PHOTO_SELECTED_NATIVE_UPLOAD_PENDING')throw Error('Photo submit already attempted');let s=await current('image');
  const dimensions=packet.photo.width+'  x  '+packet.photo.height+'  px';if(!s.includes('heading Confirm Primary Image')||!s.includes(dimensions))throw Error('Accepted image dimensions differ or upload is not ready');
  await fs.writeFile(out+'/evidence/saatchi-'+packet.catalogue_id+'-image-accepted.txt',s);intent.native_temp_image=s.match(/image \/(art_[a-z0-9]+\.jpg)/)?.[1];intent.status='ACCEPTED_IMAGE_CREATE_SUBMITTING';await save();
  await chrome.click(h.idx(s,/button Submit$/));s=await current('image');await chrome.click(next(s,'Images'));s=await current('image');intent.status='CREATE_SAVE_SUBMITTED_DO_NOT_RECREATE';intent.submitted_utc=new Date().toISOString();await save();
  await chrome.click(h.idx(s,/link Save & Continue,/));s=await h.state();return {status:intent.status,route:address(s)};
 }
 async function bind(){
  if(intent.status!=='CREATE_SAVE_SUBMITTED_DO_NOT_RECREATE')throw Error('Unexpected binding stage');let s=await focus();
  const id=address(s).match(/saatchiart\.com\/en-gb\/studio\/art\/(\d+)\/description/)?.[1];if(!id||!s.includes(packet.title)||!s.includes('text DRAFT'))throw Error('Saved native creation not yet reconciled');
  intent.native_artwork_id=id;intent.status='SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED';intent.saved_utc=new Date().toISOString();await save();await fs.writeFile(out+'/evidence/saatchi-'+id+'-description-initial.txt',s);return {native_id:id,sku:packet.sku,intent_path:intentPath};
 }
 async function refreshDescription(){
  if(intent.status!=='SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED')throw Error('Only a newly bound, unedited description can be refreshed');
  const s=await current('description');if(!/text field \(settable\) Search or select a category$/.test(s.split('\n').find(x=>x.includes('text field')&&x.includes('Search or select a category'))||''))throw Error('Server form already contains description data');
  await chrome.click(h.idx(s,/button Reload$/));intent.description_form_refreshed_utc=new Date().toISOString();await save();let after=await h.state();if(after.includes('Reload site? Changes that you made may not be saved.')){await chrome.click(h.idx(after,/button Reload, ID: action-button-1$/));after=await h.state();}return {status:'NORMAL_DESCRIPTION_RELOAD_SUBMITTED',native_id:intent.native_artwork_id,route:address(after)};
 }
 async function refreshPrice(){
  if(intent.status!=='DESCRIPTION_SAVE_SUBMITTED_EXISTING_ID')throw Error('Only the new unedited sale form may be refreshed');const s=await current('price-details');if(!s.includes('radio button Not For Sale, Value: 1')||s.includes('stepper (settable, float)'))throw Error('Sale form already contains values; reconcile before refreshing');await chrome.click(h.idx(s,/button Reload$/));intent.price_form_refreshed_utc=new Date().toISOString();await save();let after=await h.state();if(after.includes('Reload site? Changes that you made may not be saved.')){await chrome.click(h.idx(after,/button Reload, ID: action-button-1$/));after=await h.state();}return {status:'NORMAL_PRICE_FORM_RELOAD_SUBMITTED',native_id:intent.native_artwork_id,route:address(after)};
 }
 async function description(keywords,{nativeKeyboard=false}={}){
  if(intent.status!=='SAVED_PRIMARY_DRAFT_NATIVE_ID_VERIFIED')throw Error('Description has already been attempted');let s=await expanded('description','Category, Subject, Year');
  const enter=async(index,value,numeric=false)=>{if(nativeKeyboard){await chrome.click(index);await chrome.pressKey('super+a');if(numeric)await chrome.typeText(String(value));else await chrome.paste(String(value),{format:'text'});await chrome.pressKey('Tab');}else await chrome.setValue(index,String(value));return current('description');};
  s=await dropdown(s,'Search or select a category','Sculpture');s=await dropdown(s,'Search or select a subject','Abstract');await chrome.click(h.idx(s,/pop-up button Select year produced$/));s=await h.state();await chrome.click(h.idx(s,/2026, ID: menuItemSelected:$/));s=await current('description');await chrome.click(next(s,'Category, Subject, Year'));s=await expanded('description','Method, Materials & Styles');
  s=await dropdown(s,'Search or select a metho','Relief');s=await dropdown(s,'Search or select a material','Plaster');s=await dropdown(s,'Search or select a style','Abstract');await chrome.click(next(s,'Method, Materials & Styles'));s=await expanded('description','Dimensions');
  for(const [label,value] of [['Width',packet.dimensions_cm[0]],['Height',packet.dimensions_cm[1]],['Depth',packet.dimensions_cm[2]]]){s=await enter(dimension(s,label),value,true);if(dimensionValue(s,label)!==Number(value))throw Error('Dimension did not survive input/blur: '+label);}
  await chrome.click(next(s,'Dimensions'));s=await expanded('description','Keywords & Description');s=await enter(h.idx(s,/text field \(settable\) Enter Up To 12 Keywords$/),keywords.join(', '));await chrome.click(h.idx(s,/button Add$/));s=await current('description');
  s=await enter(h.idx(s,/text entry area \(settable\) Write Here\.\.\.$/),packet.description);if(!s.includes(packet.description))throw Error('Exact full description input not retained');
  intent.description_input_method=nativeKeyboard?'visible-sections-native-numeric-typing-and-plain-text-paste-with-blur':'native-accessibility-value-with-visible-section-and-value-checks';await save();
  await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-description-filled.txt',s);await chrome.click(next(s,'Keywords & Description'));s=await current('description');intent.status='DESCRIPTION_SAVE_SUBMITTED_EXISTING_ID';intent.description_characters=packet.description.length;await save();await chrome.click(h.idx(s,/link Save & Continue,/));s=await h.state();return {status:intent.status,route:address(s)};
 }
 async function saleBasics(){
  if(intent.status!=='DESCRIPTION_SAVE_SUBMITTED_EXISTING_ID')throw Error('Unexpected sale stage');let s=await current('price-details');await chrome.click(h.idx(s,/radio button For Sale, Value: 0$/));s=await current('price-details');await chrome.click(h.idx(s,/radio button Limited Edition, Value: 0$/));s=await current('price-details');intent.status='LIMITED_EDITION_FORM_EXPANDING';await save();return {status:intent.status,sku:packet.sku};
 }
 async function price(){
  if(intent.status!=='LIMITED_EDITION_FORM_EXPANDING')throw Error('Unexpected packing stage');let s=await current('price-details');
  const typeNumber=async(pattern,value)=>{await chrome.click(h.idx(s,pattern));await chrome.pressKey('super+a');await chrome.typeText(String(value));await chrome.pressKey('Tab');s=await current('price-details');};
  await typeNumber(/stepper.*(?:Placeholder: Enter Total Run|\) Enter Total Run)$/,'50');
  await chrome.click(radio(s,'Is the artwork displayed in multiple pieces?','No'));s=await current('price-details');await chrome.click(radio(s,'Is the artwork primarily wall-mounted or free-standing?','Wall-Mounted'));s=await current('price-details');
  await chrome.click(radio(s,'Does the artwork come with installed hardware, ready to hang?','No'));s=await current('price-details');await chrome.click(radio(s,'Is this artwork suitable/safe for the outdoors?','Yes'));s=await current('price-details');
  await chrome.click(h.idx(s,/stepper.*(?:Placeholder: Enter Availability|\) Enter Availability)$/));await chrome.pressKey('super+a');await chrome.typeText('1');await chrome.pressKey('Tab');s=await current('price-details');if(h.value(s,/stepper.*Placeholder: Enter Availability/)!=='1'){await chrome.getScreenshot({emit:false});s=await current('price-details');}if(h.value(s,/stepper.*Placeholder: Enter Availability/)!=='1')throw Error('Availability not retained');
  await chrome.click(next(s,'Additional Details'));s=await current('price-details');await chrome.click(h.idx(s,/radio button Crate, Value: 0$/));s=await current('price-details');await typeNumber(/stepper.*(?:Placeholder: Enter weight|\) Enter weight)$/,packet.native_packed_weight_kg_estimate);await chrome.click(next(s,'Weight and Packaging'));s=await current('price-details');
  await chrome.click(h.idx(s,/radio button Sally Price Court Essington[^\n]+Value: 0$/));s=await current('price-details');await chrome.click(next(s,'Shipping Address'));s=await current('price-details');await typeNumber(/stepper.*(?:Placeholder: Enter price|\) Enter price)$/,packet.target_artwork_price_usd);
  for(const [re,val]of [[/stepper.*Placeholder: Enter Total Run/,'50'],[/stepper.*Placeholder: Enter Availability/,'1'],[/stepper.*Placeholder: Enter weight/,String(packet.native_packed_weight_kg_estimate)],[/stepper.*Placeholder: Enter price/,String(packet.target_artwork_price_usd)]])if(h.value(s,re)!==val)throw Error('Price/quantity input mismatch');
  await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-price-staged.txt',s);await chrome.click(next(s,'Price'));s=await current('price-details');intent.status='PRICE_AND_PACKING_READY_FOR_NATIVE_QUOTE';intent.edition_size=50;intent.available_units=1;intent.ready_to_hang_claimed=false;await save();return {status:intent.status,price_usd:packet.target_artwork_price_usd,packed_kg:packet.native_packed_weight_kg_estimate,route:address(s)};
 }
 async function savePriceWhenQuoted(){
  if(intent.status!=='PRICE_AND_PACKING_READY_FOR_NATIVE_QUOTE')throw Error('Price was already submitted or is not staged');let s=await current('price-details');const visible=ax(s);const quote=visible.match(/Shipping Cost to\s+United States\s+Paid by Collector\s+US\$\s*([\d,]+(?:\.\d+)?)/);const quoteUsd=quote?Number(quote[1].replace(/,/g,'')):NaN;if(!Number.isFinite(quoteUsd)||quoteUsd<=0)return {status:'WAIT_FOR_NATIVE_SHIPPING_QUOTE',native_id:intent.native_artwork_id};
  for(const [re,val]of [[/stepper.*Placeholder: Enter Total Run/,'50'],[/stepper.*Placeholder: Enter Availability/,'1'],[/stepper.*Placeholder: Enter weight/,String(packet.native_packed_weight_kg_estimate)],[/stepper.*Placeholder: Enter price/,String(packet.target_artwork_price_usd)]])if(h.value(s,re)!==val)throw Error('Staged numeric value changed before Save');
  await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-native-shipping-quote.txt',s);intent.status='PRICE_AND_PACKING_SAVE_SUBMITTED_EXISTING_ID';intent.native_us_shipping_quote_usd=quoteUsd;intent.price_saved_by='One visible Save and Continue activation after a positive native shipping quote';await save();await chrome.click(h.idx(s,/link Save & Continue,/));s=await h.state();return {status:intent.status,price_usd:packet.target_artwork_price_usd,native_us_shipping_quote_usd:quoteUsd,route:address(s)};
 }
 async function overview(){
  let s=await current('prints');if(!s.includes('radio button Not For Sale, Value: 1'))throw Error('Prints setting differs');await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-prints-after-price-save.txt',s);await chrome.click(h.idx(s,/button Back to Overview$/));s=await h.state();return {status:'OVERVIEW_NAVIGATION_SUBMITTED',route:address(s)};
 }
 async function verifyAndPublish(){
  if(intent.status!=='PRICE_AND_PACKING_SAVE_SUBMITTED_EXISTING_ID')throw Error('Publication already submitted or unexpected stage');let s=await current('overview');
  if(!ax(s).includes('Visibility:  Draft')||!s.includes('Artwork Price $'+packet.target_artwork_price_usd)||!s.includes('Shipping Weight '+packet.native_packed_weight_kg_estimate+' kg')||!s.includes('Quantity Total Run 50 Sold on Saatchi Art 0 For Sale 1'))throw Error('Saved sale details differ');
  if(!s.includes('Ready to Hang No')||!s.includes('Outdoor Safe Yes'))throw Error('Saved installation fields differ');await chrome.click(h.idx(s,/button READ MORE$/));s=await current('overview');await chrome.click(h.idx(s,/heading Description, Value: 2$/));await chrome.pressKey('super+a');s=await current('overview');const selected=s.match(/Selected text: ```\n([\s\S]*?)\n```/)?.[1];if(!selected||!norm(selected).includes(norm(packet.description)))throw Error('Full saved description differs');
  await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-overview-verified.txt',s);intent.status='PUBLISH_SUBMITTED_EXISTING_ID_DO_NOT_RETRY';intent.details_verified_utc=new Date().toISOString();intent.publish_submitted_utc=new Date().toISOString();await save();await chrome.click(h.idx(ax(s),/button Publish$/));s=await h.state();return {status:intent.status,native_id:intent.native_artwork_id,route:address(s)};
 }
 async function publication(){
  let s=await current('overview');if(!ax(s).includes('text Visibility:  Published'))throw Error('Publication not yet confirmed; do not retry');await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-after-publish-readback.txt',s);intent.status='PUBLISHED_NATIVE_READBACK_VERIFIED';intent.published_verified_utc=new Date().toISOString();await save();await fs.writeFile(out+'/evidence/saatchi-'+intent.native_artwork_id+'-published.png',await chrome.getScreenshot({emit:false}));return {status:intent.status,native_id:intent.native_artwork_id,sku:packet.sku,intent_path:intentPath};
 }
 return {start,resume,photo,acceptPhoto,bind,refreshDescription,refreshPrice,description,saleBasics,price,savePriceWhenQuoted,overview,verifyAndPublish,publication};
}
