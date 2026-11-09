'use strict';
const $ = (id) => document.getElementById(id);
let config, draft, currentOrder;
const money = (value) => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(Number(value));
function notice(message, kind='') { $('notice').hidden=!message; $('notice').textContent=message; $('notice').className=kind; }
function progress(step) { [1,2,3].forEach(n=>$('step'+n).classList.toggle('active',n<=step)); }
function node(tag, text, cls) { const el=document.createElement(tag); el.textContent=text; if(cls) el.className=cls; return el; }
async function api(path, data) {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':config.csrf},body:JSON.stringify(data)});
  const body=await response.json(); if(!response.ok) throw new Error(body.error||'The request failed. Please retry.'); return body;
}
function showCart(data) {
  draft=data; $('empty-cart').hidden=true; $('receipt').hidden=true; $('payment-return').hidden=true; $('cart-content').hidden=false;
  $('order-state').textContent='READY FOR REVIEW'; $('line-items').replaceChildren();
  data.items.forEach(item=>{const row=node('div','','line-item'); const desc=node('div',''); desc.append(node('strong',item.name),node('small',`${item.quantity} × ${money(item.unit_price)}`)); row.append(desc,node('span',money(item.subtotal),'line-price')); $('line-items').append(row);});
  $('total').textContent=money(data.total); $('budget-note').textContent=data.budget?`✓ Within your ${money(data.budget)} budget`:''; progress(2);
}
function showReceipt(data) {
  $('empty-cart').hidden=true; $('cart-content').hidden=true; $('payment-return').hidden=true; $('receipt').hidden=false;
  $('order-state').textContent='CAPTURE COMPLETED'; $('receipt').replaceChildren(node('div','✓','receipt-icon'),node('h2','Payment verified.','receipt-title'),node('p','Your PayPal sandbox payment is complete.','muted'),node('div',`${money(data.total)} USD`,'receipt-total'));
  const dl=node('dl','','receipt-meta');
  [['Environment','SANDBOX · No real funds'],['PayPal order',data.order_id],['Capture ID',data.capture_id],['Capture status',data.status],['Completed at',data.completed_at||'Verified by PayPal']].forEach(([label,value])=>{const div=node('div','');div.append(node('dt',label),node('dd',value));dl.append(div);});
  const restart=node('button','Start another order ↗','restart');restart.addEventListener('click',()=>location.assign('/'));$('receipt').append(dl,restart); progress(3); notice('');
}
$('prompt').addEventListener('input',()=>{$('char-count').textContent=`${$('prompt').value.length} / 1000`;});
$('prompt').addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key==='Enter'){event.preventDefault();$('intent-form').requestSubmit();}});
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{$('prompt').value=button.dataset.example;$('prompt').dispatchEvent(new Event('input'));$('prompt').focus();}));
$('intent-form').addEventListener('submit',async event=>{
  event.preventDefault(); if(!config) return; $('generate').disabled=true;$('pay').disabled=true; draft=null;
  $('cart-content').hidden=true; $('receipt').hidden=true; $('empty-cart').hidden=false; $('payment-return').hidden=true;
  $('order-state').textContent='UNDERSTANDING INTENT';progress(1);notice('AI is reading your request and matching products…','loading');
  try {const data=await api('/api/interpret',{prompt:$('prompt').value});if(data.clarification){notice(data.clarification);$('order-state').textContent='NEEDS CLARIFICATION';}else{showCart(data);notice('Your cart is ready. Review the items and total before continuing.');}}
  catch(error){notice(error.message,'error');$('order-state').textContent='AWAITING INTENT';}
  finally{$('generate').disabled=false;$('pay').disabled=false;}
});
$('pay').addEventListener('click',async()=>{
  if(!draft)return; $('pay').disabled=true;$('generate').disabled=true;notice('Creating your PayPal sandbox order…','loading');
  try{const data=await api('/api/create-order',{draft_id:draft.draft_id});const url=new URL(data.approval_url);if(url.protocol!=='https:'||!['www.sandbox.paypal.com','sandbox.paypal.com'].includes(url.hostname))throw new Error('Only PayPal sandbox approval links are allowed.');sessionStorage.setItem('intentcart_order',data.order_id);location.assign(url.href);}
  catch(error){notice(error.message,'error');$('pay').disabled=false;$('generate').disabled=false;}
});
async function verify() {
  $('verify').disabled=true;notice('Checking the order and capturing the approved sandbox payment…','loading');
  try{const data=await api('/api/capture',{order_id:currentOrder});showReceipt(data);sessionStorage.removeItem('intentcart_order');history.replaceState(null,'','/');}
  catch(error){notice(error.message,'error');$('verify').disabled=false;}
}
$('verify').addEventListener('click',verify);
(async()=>{
  try{const res=await fetch('/api/config');config=await res.json();if(!res.ok)throw new Error(config.error||'Configuration unavailable.');
    $('catalog-grid').replaceChildren();config.catalog.forEach(p=>{const el=node('article','','product');el.append(node('span',p.symbol,'product-number'),node('h3',p.name),node('p',p.detail),node('strong',money(p.price)));$('catalog-grid').append(el);});
    const missing=[];if(!config.ai_ready)missing.push('AI key');if(!config.paypal_ready)missing.push('PayPal sandbox credentials');$('connection-state').textContent=missing.length?`Setup needed: ${missing.join(' + ')}`:'Cloud AI + PayPal sandbox · configured';
    const params=new URLSearchParams(location.search);
    if(params.get('checkout')==='cancel'){notice('Checkout canceled. No capture was requested. Describe your order to try again.');history.replaceState(null,'','/');}
    else if(params.get('checkout')==='return'){
      currentOrder=params.get('token');$('empty-cart').hidden=true;$('payment-return').hidden=false;$('order-state').textContent='VERIFYING WITH PAYPAL';progress(3);
      if(!currentOrder){notice('PayPal did not return an order identifier. Return to the original checkout.','error');$('verify').disabled=true;}else await verify();
    }
  }catch(error){notice(error.message,'error');$('connection-state').textContent='Connection unavailable';}
})();
