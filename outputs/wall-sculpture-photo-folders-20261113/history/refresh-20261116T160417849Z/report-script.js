
const search=document.getElementById('search'),showAll=document.getElementById('showAll'),rows=[...document.querySelectorAll('#photoFolders tbody tr')];
function update(){let count=0;for(const row of rows){row.hidden=!(row.dataset.search.includes(search.value.toLowerCase())&&(showAll.checked||row.dataset.empty==='true'));if(!row.hidden)count++;}document.getElementById('count').textContent=count+' component and finish folders';}
search.addEventListener('input',update);showAll.addEventListener('change',update);update();
const inSituSearch=document.getElementById('inSituSearch'),dedicatedOnly=document.getElementById('dedicatedOnly'),inSituRows=[...document.querySelectorAll('#inSituTable tbody tr')];
function updateInSitu(){let count=0;for(const row of inSituRows){row.hidden=!(row.dataset.search.includes(inSituSearch.value.toLowerCase())&&(dedicatedOnly.checked||row.dataset.status==='missing'));if(!row.hidden)count++;}document.getElementById('inSituCount').textContent=count+' component and finish entries';}
inSituSearch.addEventListener('input',updateInSitu);dedicatedOnly.addEventListener('change',updateInSitu);updateInSitu();
