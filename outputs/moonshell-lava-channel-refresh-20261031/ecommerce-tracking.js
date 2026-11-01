/* Boldstone GA4 shopping funnel, 2026-10-31.
 * Supplements native Squarespace purchase tracking. Does not send Meta events,
 * purchase events, customer details, cart tokens, or duplicate page views.
 * A cart addition requires a genuine click AND a confirmed cart-count increase.
 */
(function () {
  'use strict';
  if (window.__boldstoneShoppingFunnel) return;
  window.__boldstoneShoppingFunnel = true;
  var lastView = '', pending = null, checkoutAt = 0, scheduled = false;
  function consent() {
    try { return window.getSquarespaceCookies().performance === 'accepted'; }
    catch (_) { return false; }
  }
  function emit(name, items, currency) {
    if (!consent() || typeof window.gtag !== 'function' || !items.length) return false;
    if (!/^[A-Z]{3}$/.test(currency)) return false;
    if (items.some(function (i) {
      return !i.item_id || !i.item_name || !Number.isFinite(i.price) || i.price < 0 ||
        !Number.isInteger(i.quantity) || i.quantity < 1;
    })) return false;
    window.gtag('event', name, {
      send_to: 'G-DYE31M1PWM', currency: currency,
      value: Math.round(items.reduce(function (n, i) { return n + i.price * i.quantity; }, 0) * 100) / 100,
      items: items, transport_type: 'beacon'
    });
    return true;
  }
  function product() {
    if (!document.querySelector('.sqs-add-to-cart-button')) return null;
    var results = [];
    document.querySelectorAll('script[type="application/ld+json"]').forEach(function (s) {
      try {
        var p = JSON.parse(s.textContent);
        // Single-offer products only: never guess the chosen multi-variant SKU.
        if (p['@type'] !== 'Product' || !p.offers || Array.isArray(p.offers) || p.offers['@type'] !== 'Offer') return;
        var o = p.offers;
        if (!o.sku || o.price == null || o.price === '') return;
        if (new URL(o.url, location.href).pathname !== location.pathname) return;
        results.push({currency: o.priceCurrency, item: {
          item_id: String(o.sku), item_name: String(p.name).replace(/\s+[—–]\s+boldstone$/i, ''),
          item_brand: 'Boldstone', price: Number(o.price), quantity: 1
        }});
      } catch (_) { /* Leave malformed or ambiguous products uncounted. */ }
    });
    return results.length === 1 ? results[0] : null;
  }
  function count() {
    var values = Array.from(document.querySelectorAll('.sqs-cart-initialized .sqs-cart-quantity')).map(function (e) { return Number(e.textContent.trim()); });
    if (!values.length || values.some(function (n) { return !Number.isInteger(n) || n < 0 || n !== values[0]; })) return null;
    return values[0];
  }
  function cart() {
    if (location.pathname !== '/cart') return null;
    var context = document.querySelector('#sqs-cart-root > script[type="application/json"]');
    if (!context) return null;
    try {
      var source = JSON.parse(context.textContent);
      if (source.storeCurrency !== 'GBP') return null;
      var rows = Array.from(document.querySelectorAll('[data-testid="cart-table-row"]'));
      if (!rows.length) return null;
      var items = rows.map(function (row) {
        var link = row.querySelector('.cart-row-title');
        var input = row.querySelector('.cart-row-qty-input');
        var total = row.querySelector('.cart-row-price');
        if (!link || !input || !total) throw new Error('Incomplete cart row');
        var matches = source.cart.items.filter(function (i) {
          return new URL(i.productUrl, location.href).pathname === new URL(link.href).pathname;
        });
        if (matches.length !== 1) throw new Error('Ambiguous cart variant');
        var item = matches[0], quantity = Number(input.value);
        if (!item.sku || !item.unitPrice || !item.unitPrice.decimalValue) throw new Error('Missing cart price or SKU');
        var price = Number(item.unitPrice.decimalValue);
        var visibleTotal = Number(total.textContent.replace(/[£,\s]/g, ''));
        if (item.unitPrice.currencyCode !== 'GBP' || Math.abs(visibleTotal - price * quantity) > 0.005) throw new Error('Cart not settled');
        return {item_id: String(item.sku), item_name: item.productName, item_brand: 'Boldstone', price: price, quantity: quantity};
      });
      return {items: items, currency: 'GBP'};
    } catch (_) { return null; }
  }
  function check() {
    scheduled = false;
    if (!consent()) { pending = null; return; }
    var p = product(), c = cart();
    var key = location.pathname + ':' + (p ? p.item.item_id : c ? 'cart' : '');
    if (key !== lastView) {
      if (p && emit('view_item', [p.item], p.currency)) lastView = key;
      else if (c && emit('view_cart', c.items, c.currency)) lastView = key;
    }
    if (pending) {
      if (Date.now() - pending.at > 30000 || pending.path !== location.pathname || !pending.button.isConnected) { pending = null; return; }
      var after = count();
      if (after !== null && after > pending.before) {
        var addition = pending; pending = null;
        // Other tab changes or unexpected quantities must not create false events.
        if (after - addition.before === 1) emit('add_to_cart', [addition.product.item], addition.product.currency);
      }
    }
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(check, 100);
  }
  function click(e) {
    if (!e.isTrusted || !e.target.closest || !consent()) return;
    if (pending && Date.now() - pending.at > 30000) pending = null;
    var button = e.target.closest('.sqs-add-to-cart-button');
    if (button && !button.disabled && !button.classList.contains('cart-adding')) {
      var p = product(), before = count();
      if (p && before !== null && !pending) pending = {product:p, before:before, at:Date.now(), path:location.pathname, button:button};
    }
    var checkout = e.target.closest('a.cart-checkout-button[href]');
    if (checkout && new URL(checkout.href).pathname === '/commerce/goto-checkout' && Date.now() - checkoutAt > 3000) {
      var c = cart();
      if (c && emit('begin_checkout', c.items, c.currency)) checkoutAt = Date.now();
    }
  }
  function start() {
    document.addEventListener('click', click, true);
    new MutationObserver(schedule).observe(document.body, {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['class','value']});
    var previous = window.onCookieBannerInteraction;
    window.onCookieBannerInteraction = function () {
      try { if (typeof previous === 'function') previous.apply(this, arguments); }
      finally { schedule(); }
    };
    window.addEventListener('pageshow', function (event) {
      // Initial pageshow follows DOMContentLoaded; resetting then duplicates views.
      if (!event.persisted) return;
      pending = null; checkoutAt = 0; lastView = ''; schedule();
    });
    check();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
