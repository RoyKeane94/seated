(function () {
  var currentScript = document.currentScript;
  if (!currentScript) return;

  var slug = currentScript.getAttribute('data-restaurant');
  if (!slug) return;

  var origin = currentScript.src.split('/static/js/widget.js')[0];
  var iframe = document.createElement('iframe');
  iframe.src = origin + '/book/' + slug + '/?embedded=true';
  iframe.style.width = '100%';
  iframe.style.border = '0';
  iframe.style.minHeight = '600px';
  iframe.style.overflow = 'hidden';
  iframe.setAttribute('loading', 'lazy');

  currentScript.parentNode.insertBefore(iframe, currentScript);

  window.addEventListener('message', function (event) {
    if (!event.data || event.data.type !== 'seated:height') return;
    iframe.style.height = Math.max(400, Number(event.data.height || 0)) + 'px';
  });
})();
