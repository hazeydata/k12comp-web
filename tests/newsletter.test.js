"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { attach, MESSAGES } = require("../newsletter.js");

function setup(fetchImpl, emailValue = "a@b.org", hpValue = "") {
  let handler;
  const attrs = {};
  const email = {
    value: emailValue, disabled: false, focused: 0,
    setAttribute(k, v) { attrs[k] = v; }, removeAttribute(k) { delete attrs[k]; },
    focus() { this.focused++; }
  };
  const status = {
    className: "nl-status", textContent: "", attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }
  };
  const button = { disabled: false };
  const calls = [];
  const form = { addEventListener(t, h) { assert.equal(t, "submit"); handler = h; } };
  attach({
    form, email, button, status, honeypot: { value: hpValue },
    fetch: (url, init) => { calls.push({ url, init }); return fetchImpl(url, init); }
  });
  let prevented = 0;
  const submit = () => { handler({ preventDefault() { prevented++; } }); };
  return { email, status, button, calls, submit, attrs, prevented: () => prevented };
}
const tick = () => new Promise((r) => setImmediate(r));
const resp = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test("pending state disables controls, then re-enables on success", async () => {
  let release;
  const t = setup(() => new Promise((r) => { release = r; }));
  t.submit();
  assert.equal(t.button.disabled, true);
  assert.equal(t.email.disabled, true);
  assert.equal(t.status.textContent, MESSAGES.pending);
  assert.equal(t.status.attrs["aria-busy"], "true");
  t.submit(); // double submit ignored
  assert.equal(t.calls.length, 1);
  release(resp(200, { status: "subscribed" }));
  await tick();
  assert.equal(t.button.disabled, false);
  assert.equal(t.email.disabled, false);
  assert.equal(t.status.attrs["aria-busy"], undefined);
});

test("request body, headers, endpoint, source and honeypot", async () => {
  const t = setup(async () => resp(200, { status: "subscribed" }), "  Me@District.org ", "bot");
  t.submit();
  await tick();
  const { url, init } = t.calls[0];
  assert.equal(url, "https://hazeydata.ai/api/subscribe");
  assert.equal(init.method, "POST");
  assert.equal(init.headers.Accept, "application/json");
  assert.equal(init.headers["Content-Type"], "application/x-www-form-urlencoded");
  assert.equal(init.credentials, "omit");
  const p = new URLSearchParams(init.body);
  assert.deepEqual([...p.keys()].sort(), ["email", "source", "website"]);
  assert.equal(p.get("email"), "Me@District.org");
  assert.equal(p.get("source"), "k12comp");
  assert.equal(p.get("website"), "bot");
});

test("empty honeypot is sent as empty website field", async () => {
  const t = setup(async () => resp(200, { status: "subscribed" }));
  t.submit();
  await tick();
  assert.equal(new URLSearchParams(t.calls[0].init.body).get("website"), "");
});

for (const [st, msg, clears] of [
  ["subscribed", "You're on the list.", true],
  ["already_subscribed", "You're already on the list.", true],
  ["pending_confirmation", "Your subscription is pending confirmation.", false]
]) {
  test(`status ${st}`, async () => {
    const t = setup(async () => resp(200, { status: st }));
    t.submit();
    await tick();
    assert.equal(t.status.textContent, msg);
    assert.equal(t.status.className, "nl-status ok");
    assert.equal(t.email.value, clears ? "" : "a@b.org");
    assert.equal(t.button.disabled, false);
    assert.equal(t.email.disabled, false);
  });
}

test("pending_confirmation is never reported as subscribed", async () => {
  const t = setup(async () => resp(200, { status: "pending_confirmation" }));
  t.submit();
  await tick();
  assert.notEqual(t.status.textContent, MESSAGES.subscribed);
  assert.notEqual(t.status.textContent, MESSAGES.already_subscribed);
});

test("client-side malformed email: no request, invalid message", () => {
  for (const bad of ["", "   ", "nope", "a@b", "a b@c.org"]) {
    const t = setup(async () => resp(200, { status: "subscribed" }), bad);
    t.submit();
    assert.equal(t.calls.length, 0);
    assert.equal(t.status.textContent, "That email doesn't look right. Try again.");
    assert.equal(t.status.className, "nl-status err");
    assert.equal(t.email.value, bad);
    assert.equal(t.prevented(), 1);
  }
});

test("server invalid response shows invalid message and keeps email", async () => {
  for (const [code, body] of [[400, { status: "invalid_email" }], [422, { status: "invalid_email" }]]) {
    const t = setup(async () => resp(code, body));
    t.submit();
    await tick();
    assert.equal(t.status.textContent, "That email doesn't look right. Try again.");
    assert.equal(t.email.value, "a@b.org");
    assert.equal(t.button.disabled, false);
    assert.equal(t.email.disabled, false);
  }
});

const FAIL = "Something broke on our end. Try again in a minute.";
test("network failure, thrown fetch, HTTP errors and malformed bodies are service failures", async () => {
  const cases = {
    reject: () => Promise.reject(new TypeError("Failed to fetch")),
    throws: () => { throw new Error("boom"); },
    http500: async () => resp(500, { status: "error" }),
    http200Error: async () => resp(200, { status: "error" }),
    unknownStatus: async () => resp(200, { status: "weird" }),
    okButInvalidName: async () => resp(200, { status: "invalid_email" }),
    nonJson: async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } }),
    nullBody: async () => resp(200, null),
    noStatus: async () => resp(200, {}),
    invalid500: async () => resp(500, { status: "invalid_email" }),
    invalidOtherStatus: async () => resp(400, { status: "invalid" }),
    errorFieldNotStatus: async () => resp(200, { error: "subscribed" }),
    rateLimited: async () => resp(429, { status: "rate_limited" }),
    redirect302: async () => resp(302, { status: "subscribed" }),
    errorOn5xxSubscribedBody: async () => resp(502, { status: "subscribed" })
  };
  for (const [name, impl] of Object.entries(cases)) {
    const t = setup(impl);
    t.submit();
    await tick();
    assert.equal(t.status.textContent, FAIL, name);
    assert.equal(t.status.className, "nl-status err", name);
    assert.equal(t.email.value, "a@b.org", name);
    assert.equal(t.button.disabled, false, name);
    assert.equal(t.email.disabled, false, name);
  }
});

test("HTTP 400 invalid_email from backend shows exact invalid message, never success", async () => {
  const t = setup(async () => resp(400, { status: "invalid_email" }), "x@y.zz");
  t.submit();
  await tick();
  assert.equal(t.status.textContent, MESSAGES.invalid);
  assert.equal(t.status.className, "nl-status err");
  assert.equal(t.attrs["aria-invalid"], "true");
  assert.equal(t.email.value, "x@y.zz");
  assert.equal(t.email.focused, 1);
});

test("bootstrap wires a district-page form with mocked fetch (source k12comp, no live request)", async () => {
  const fs = require("node:fs");
  const page = fs.readFileSync(__dirname + "/../nj/edison-twp-3404500/index.html", "utf8");
  assert.match(page, /<form class="nl-form" action="https:\/\/hazeydata\.ai\/api\/subscribe"/);
  assert.match(page, /<script src="\/newsletter\.js" defer><\/script>/);
  let handler;
  const mk = (extra) => Object.assign({ value: "", disabled: false, setAttribute() {}, removeAttribute() {}, focus() {} }, extra);
  const email = mk({ value: "a@b.org" }), website = mk(), button = mk(), status = mk({ className: "", textContent: "" });
  const form = {
    addEventListener(_, h) { handler = h; },
    querySelector: (q) => (q.includes("email") ? email : q.includes("website") ? website : button)
  };
  const doc = { querySelector: (q) => (q === ".newsletter form.nl-form" ? form : status) };
  const calls = [];
  const realFetch = global.fetch;
  global.fetch = (u, i) => { calls.push([u, i]); return Promise.resolve({ ok: true, status: 200, json: async () => ({ status: "subscribed" }) }); };
  try {
    require("../newsletter.js").bootstrap(doc);
    handler({ preventDefault() {} });
    await tick(); await tick();
  } finally { global.fetch = realFetch; }
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "https://hazeydata.ai/api/subscribe");
  assert.equal(new URLSearchParams(calls[0][1].body).get("source"), "k12comp");
  assert.equal(status.textContent, MESSAGES.subscribed);
});
