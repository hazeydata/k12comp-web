(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else api.bootstrap(root.document);
})(typeof self !== "undefined" ? self : this, function () {
  var ENDPOINT = "https://hazeydata.ai/api/subscribe";
  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var MSG = {
    pending: "Sending…",
    subscribed: "You're on the list.",
    already_subscribed: "You're already on the list.",
    pending_confirmation: "Your subscription is pending confirmation.",
    invalid: "That email doesn't look right. Try again.",
    failure: "Something broke on our end. Try again in a minute."
  };

  function say(out, cls, text) {
    out.className = "nl-status" + (cls ? " " + cls : "");
    out.textContent = text;
  }

  // Maps a fetch Response to a result key; never throws.
  function classify(res) {
    return res.json().then(function (data) {
      var st = data && typeof data === "object" ? data.status : "";
      if (res.ok && (st === "subscribed" || st === "already_subscribed" || st === "pending_confirmation")) return st;
      if ((res.status === 400 || res.status === 422) && st === "invalid_email") return "invalid";
      return "failure";
    }, function () { return "failure"; });
  }

  function attach(o) {
    var form = o.form, email = o.email, hp = o.honeypot, button = o.button, out = o.status;
    var fetchFn = o.fetch, busy = false;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (busy) return;
      var v = String(email.value).trim();
      if (!EMAIL_RE.test(v)) {
        say(out, "err", MSG.invalid);
        email.setAttribute("aria-invalid", "true");
        email.focus();
        return;
      }
      email.removeAttribute("aria-invalid");
      var body = new URLSearchParams();
      body.set("email", v);
      body.set("source", "k12comp");
      body.set("website", hp ? String(hp.value) : "");
      busy = true;
      button.disabled = true;
      email.disabled = true;
      out.setAttribute("aria-busy", "true");
      say(out, "", MSG.pending);
      var done = function (key) {
        busy = false;
        button.disabled = false;
        email.disabled = false;
        out.removeAttribute("aria-busy");
        if (key === "subscribed" || key === "already_subscribed") {
          email.value = "";
          say(out, "ok", MSG[key]);
        } else if (key === "pending_confirmation") {
          say(out, "ok", MSG[key]);
        } else {
          say(out, "err", MSG[key]);
          if (key === "invalid") email.setAttribute("aria-invalid", "true");
          email.focus();
        }
      };
      var p;
      try {
        p = Promise.resolve(fetchFn(o.endpoint || ENDPOINT, {
          method: "POST",
          mode: "cors",
          credentials: "omit",
          headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString()
        }));
      } catch (err) { p = Promise.reject(err); }
      p.then(classify).then(done, function () { done("failure"); });
    });
  }

  function bootstrap(doc) {
    if (!doc || !doc.querySelector) return;
    var form = doc.querySelector(".newsletter form.nl-form");
    if (!form || typeof fetch !== "function") return;
    attach({
      form: form,
      email: form.querySelector('input[name="email"]'),
      honeypot: form.querySelector('input[name="website"]'),
      button: form.querySelector('button[type="submit"]'),
      status: doc.querySelector(".newsletter .nl-status"),
      fetch: function (u, i) { return fetch(u, i); }
    });
  }

  return { attach: attach, bootstrap: bootstrap, classify: classify, ENDPOINT: ENDPOINT, MESSAGES: MSG };
});
