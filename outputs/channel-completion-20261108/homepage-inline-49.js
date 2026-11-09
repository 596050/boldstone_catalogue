
(function () {
  function trackContact(event) {
    if (!event.isTrusted || !event.target.closest) return;
    var link = event.target.closest('a[href]');
    if (!link) return;
    var method = link.protocol === 'mailto:' ? 'email' : link.protocol === 'tel:' ? 'phone' : '';
    var choices = typeof window.getSquarespaceCookies === 'function' ? window.getSquarespaceCookies() : {};
    if (!method || choices.performance !== 'accepted' || typeof window.gtag !== 'function') return;
    window.gtag('event', 'click_' + method, {
      send_to: 'G-DYE31M1PWM', contact_method: method, link_type: method === 'email' ? 'mailto' : 'tel'
    });
  }
  var enquiries = {
    '66ad0bcbd10c9508150d0c04': 'contact_enquiry',
    '6a40e3e9a631a0287c38ca47': 'homepage_enquiry',
    '6a0d721c1d29724366006daf': 'furnishings_enquiry'
  };
  var productEnquiries = ["6a131558e578c46cd0cf52c6","6a132f3987974039cbf79526","6a132f92deda452ffc2821f8","6a132fcaf7b04815480a3baf","6a132ff699592642010b33d1","6a1330290466a022dd09edf8","6a40df4002dbbf71649f56e6","6a40df50c4ad0b7e6b94b107","6a410e1f398d7f76f23a9a85","6a4436bf91a6bf3a0edb67ec","6a44401c0f076c231575337e","6a44405a1ec6544bcfabaef2","6a444089051d430e78c50d0b","6a4441c78131357bef2e14e2","6a4441f591a6bf3a0edfb608","6a4442212e29c63d4ae48729","6a444252979bab20e76d84bf","6a4444302ba6933c2835517e","6a4444e2de89f70a7e0f6c61","6a444528403eff765d606582","6a4445a1bfcf254515930c4c","6a4445e23948d17ac96890eb","6a44463297613b1b9a8f45ec","6a444724c4bd9157aaed5ecf","6a4447582e29c63d4ae6b87e","6a4447ac64e08c30b3ce1124","6a44cefba42c2a14dbac44d2","6a44cf3a9927185640d10da5","6a44cfa6148ba76329ea9dd6","6a44cfe04a7e03497d2f4826","6a44d0044fa8a62b86901905","6a44d02168e8482db86ef1b0","6a44d061c5585d11581dca65","6a540c2fb344bf6935f8e0ca","6a56753afccdff412e13f695","6a569aa7780e6210772fe703","6a569b68a5f2906ced1ba688","6a569c05df82cb318132256d","6a569caa856beb43fbfe5821","6a569d42f3c6220a0159ba65","6a569de0c70eaa5b0c155bc3","6a569e7621600240e7e022e2","6a569f1e9affd742a0d75476","6a569fbf88685d78581fa3d7","6a56a05aefd2ad380a06c6e9","6a56a0f915101b78ed6ff604","6a56a227ee266a0949bdf587","6a56a3ee8fc650249166e726","6a56a48903707d75ba506f69","6a56a542178cf638efe5425c","6a56a5fea64e4417a95ca033","6a56a6b761750f1ed175c9fe","6a56a756f17ff133f131bfc9","6a56a7f81d61906dbb1c637f","6a56a895e3a803172fdf9176","6a56a938fce5d4532de258b6","6a56a9d78e5bbe1dd11a3bfa","6a56aa7389931479d6733643","6a56ab1e3c3d510634480805","6a56abbb184a1647081233b2","6a56ad02e70f903430d321f4","6a56ae33da4aaa7c4e2e7148","6a56aec016ed7954b8e96a99","6a56af32431c52643ce71cd9","6a574ddbb80d077cca8eb2ff","6a574ffc18be4a7e3e592ef4","6a5750f90b0a806a28ce924e","6a575370a2c1a612731f3a69","6a5a6719d551291222fc7b9b","6a5a67d09b06540f443b4c6d","6a5a6975b1b00147acefbe80","6a5a6fceec0e676d7788cf6c","6a636a2d61429523107fd3c5","6aa5c06a2be1b2711bb656ab","6aa67715c20cf7004257259b","6aa688c79129ac4f52dfcaeb"];
  productEnquiries.forEach(function (formId) { enquiries[formId] = 'product_enquiry'; });
  var armed = {};
  function arm(event) {
    if (!event.isTrusted || !event.target.closest) return;
    var form = event.target.closest('form');
    if (!form || (event.type === 'click' && !event.target.closest('button[type="submit"], input[type="submit"]'))) return;
    var block = form.closest('.sqs-block-form');
    if (!block) return;
    var context = block.querySelector('script.sqs-form-block-context');
    if (!context) return;
    var formId;
    try { formId = JSON.parse(context.textContent).formId; } catch (error) { return; }
    if (enquiries[formId]) armed[formId] = block;
  }
  function checkSuccess() {
    Object.keys(armed).forEach(function (formId) {
      var block = armed[formId];
      var success = block.querySelector('.react-form-post-submit .form-submission-text');
      if (!success || !success.textContent.trim() || !success.getClientRects().length) return;
      delete armed[formId];
      var choices = typeof window.getSquarespaceCookies === 'function' ? window.getSquarespaceCookies() : {};
      if (choices.performance !== 'accepted' || typeof window.gtag !== 'function') return;
      window.gtag('event', 'generate_lead', {
        send_to: 'G-DYE31M1PWM',
        form_id: formId,
        form_name: enquiries[formId],
        lead_type: 'website_enquiry'
      });
    });
  }
  function start() {
    document.addEventListener('click', trackContact, true);
    document.addEventListener('submit', arm, true);
    document.addEventListener('click', arm, true);
    new MutationObserver(checkSuccess).observe(document.body, {
      childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style', 'hidden']
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
