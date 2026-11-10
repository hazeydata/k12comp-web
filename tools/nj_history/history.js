// Guide-year links on district pages: open the existing "Teacher salary guide, <year>" block and scroll to it.
// Old page markup is not edited; without JavaScript the link still lands on the existing guides section (#guides-h).
(function () {
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('.hist-guide .guide-years a');
    if (!a) return;
    var m = /Teacher%20salary%20guide%2C%20(\d{4}-\d\d)/.exec(a.getAttribute('href') || '');
    if (!m) return;
    var h = Array.prototype.find.call(document.querySelectorAll('h3'), function (x) {
      return x.textContent.indexOf('Teacher salary guide, ' + m[1]) === 0;
    });
    if (!h) return;
    ev.preventDefault();
    for (var d = h.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
    h.setAttribute('tabindex', '-1');
    h.scrollIntoView({ block: 'start' });
    h.focus({ preventScroll: true });
  });
})();
