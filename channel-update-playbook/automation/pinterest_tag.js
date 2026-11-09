/* Consent-gated Pinterest tag. Config contains public SKU/variant identities only.
 * Called by the existing confirmed-cart shopping funnel for commerce events.
 * No enhanced matching, customer email, purchase simulation or noscript bypass.
 */
(function (config) {
  'use strict';
  if (window.BoldstonePinterest || !/^\d{13}$/.test(config.tagId)) return;
  var started = false, genericSent = false, views = {}, serial = 0;
  function consent() {
    try { return window.getSquarespaceCookies().marketing === 'accepted'; }
    catch (_) { return false; }
  }
  function start() {
    if (!consent()) return false;
    if (!started) {
      if (!window.pintrk) {
        var queue = function () { queue.queue.push(Array.prototype.slice.call(arguments)); };
        queue.queue = []; queue.version = '3.0'; window.pintrk = queue;
        var script = document.createElement('script');
        script.async = true; script.src = 'https://s.pinimg.com/ct/core.js';
        document.head.appendChild(script);
      }
      window.pintrk('setconsent', true);
      window.pintrk('load', config.tagId);
      window.pintrk('page');
      started = true;
    }
    return true;
  }
  function commerce(name, items, currency) {
    var event = {view_item:'pagevisit', add_to_cart:'addtocart', begin_checkout:'initiatecheckout'}[name];
    if (!event || !consent() || currency !== 'GBP' || !Array.isArray(items) || !items.length) return false;
    // Do not guess another product, selected variant or a mixed-cart total.
    if (items.some(function (item) {
      return !Object.prototype.hasOwnProperty.call(config.products,item.item_id) ||
        (name === 'view_item' && config.products[item.item_id].path !== location.pathname) ||
        !Number.isFinite(item.price) || item.price < 0 ||
        !Number.isInteger(item.quantity) || item.quantity < 1;
    })) return false;
    if (!start()) return false;
    var key = location.pathname + ':' + items.map(function (i) { return i.item_id; }).join(',');
    if (event === 'pagevisit' && views[key]) return true;
    var data = {currency:currency, value:Math.round(items.reduce(function (n,i) { return n+i.price*i.quantity; },0)*100)/100,
      order_quantity:items.reduce(function (n,i) { return n+i.quantity; },0),
      event_id:'boldstone-' + Date.now() + '-' + (++serial),
      line_items:items.map(function (i) { return {
        product_id:config.products[i.item_id].id, product_name:i.item_name,
        product_price:i.price, product_quantity:i.quantity,
        product_category:'Wall Sculptures', product_brand:'Boldstone'
      }; })};
    window.pintrk('track', event, data);
    if (event === 'pagevisit') views[key] = true;
    return true;
  }
  function sync() {
    if (consent()) {
      start();
      window.pintrk('setconsent', true);
      // Product PageVisit comes from the existing JSON-LD-verified funnel.
      var productPage = Object.keys(config.products).some(function (sku) {
        return config.products[sku].path === location.pathname;
      });
      if (!productPage && !genericSent && document.readyState !== 'loading') {
        window.pintrk('track','pagevisit',{event_id:'boldstone-page-'+Date.now()+'-'+(++serial)});
        genericSent = true;
      }
    } else if (started && typeof window.pintrk === 'function') {
      window.pintrk('setconsent', false);
    }
  }
  window.BoldstonePinterest = {commerce:commerce, syncConsent:sync};
  var previous = window.onCookieBannerInteraction;
  window.onCookieBannerInteraction = function () {
    var result;
    try { if (typeof previous === 'function') result = previous.apply(this,arguments); }
    finally { sync(); }
    return result;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',sync,{once:true});
  sync();
})(__BOLDSTONE_PINTEREST_CONFIG__);
