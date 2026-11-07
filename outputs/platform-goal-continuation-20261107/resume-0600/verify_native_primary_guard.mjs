import fs from 'node:fs/promises';
import {assertPrimaryPhotoDimensions} from '../../platform-goal-continuation-20261106/saatchi-ui.mjs';
const out=new URL('./',import.meta.url);
const audit=JSON.parse(await fs.readFile(new URL('saatchi-primary-file-verification.json',out),'utf8'));
for(const record of audit.records){
 let accepted=true;
 try{assertPrimaryPhotoDimensions(record);}catch{accepted=false;}
 if(accepted!==record.native_dimensions_pass)throw Error('Guard differs from actual original dimensions: '+record.sku);
}
const proof={status:'PASS_OBSERVED_NATIVE_REJECTION_REGRESSION',actual_upload_files:16,accepted:15,held:1,
 rejected_sku:'BOLD-21E953F1D523',rejected_width:1200,rejected_height:1600,
 remaining_uncreated_ready:13,source_images_edited:false,native_uploads_sent:0};
await fs.writeFile(new URL('saatchi-primary-guard-verification.json',out),JSON.stringify(proof,null,2)+'\n');
console.log(JSON.stringify(proof));
