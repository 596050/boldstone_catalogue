
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {
  analytics_storage: 'denied', ad_storage: 'denied',
  ad_user_data: 'denied', ad_personalization: 'denied', wait_for_update: 500
});
(function () {
  var pixelStarted = false;
  function clearTrackingCookies(pattern) {
    var names = document.cookie.split(';').map(function (cookie) {
      return cookie.trim().split('=')[0];
    }).filter(function (name) { return pattern.test(name); });
    var domains = ['', '; domain=' + location.hostname, '; domain=.boldstonesculpture.com'];
    names.forEach(function (name) {
      domains.forEach(function (domain) {
        document.cookie = name + '=; Max-Age=0; path=/' + domain + '; SameSite=Lax; Secure';
      });
    });
  }
  function syncConsent() {
    var choices = {};
    if (typeof window.getSquarespaceCookies === 'function') choices = window.getSquarespaceCookies() || {};
    var marketing = choices.marketing === 'accepted';
    gtag('consent', 'update', {
      analytics_storage: choices.performance === 'accepted' ? 'granted' : 'denied',
      ad_storage: marketing ? 'granted' : 'denied',
      ad_user_data: marketing ? 'granted' : 'denied',
      ad_personalization: marketing ? 'granted' : 'denied'
    });
    if (marketing && !pixelStarted) {
      pixelStarted = true;
      if (!window.oaiq) {
        var q = function () { q.q.push(arguments); };
        q.q = [];
        window.oaiq = q;
        var script = document.createElement('script');
        script.async = true;
        script.src = 'https://bzrcdn.openai.com/sdk/oaiq.min.js';
        document.head.appendChild(script);
      }
      window.oaiq('consent', false);
      window.oaiq('init', {pixelId: '7h2BZq6n1ZWdWkD53Ekse7', debug: false});
    }
    if (typeof window.oaiq === 'function') window.oaiq('consent', marketing);
    if (choices.performance !== 'accepted') clearTrackingCookies(/^_ga(?:_|$)|^_gid$|^_gat(?:_|$)|^ss_(?:cid|cpvisit|cvisit|cvr|cvt)$/);
    if (!marketing) clearTrackingCookies(/^_fbp$|^_fbc$|^_gcl_|^_gac_|^__oppref$|^__obref$/);
  }
  var previous = window.onCookieBannerInteraction;
  window.onCookieBannerInteraction = function () {
    try {
      if (typeof previous === 'function') previous.apply(this, arguments);
    } finally {
      syncConsent();
    }
  };
  syncConsent();
})();
