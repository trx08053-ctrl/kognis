// Оверлей UI-замечаний (подключается прокси scripts/ui_feedback.py). Файл защищён.
(() => {
  if (window.__uif) return; window.__uif = true;
  const API = "/__ui/feedback", STYLES = %STYLES%;
  const css = document.createElement("style");
  css.textContent = `
    .__uif-hl{position:fixed;pointer-events:none;border:2px solid #e8590c;background:#e8590c22;z-index:2147483646;border-radius:3px}
    .__uif-tag{position:fixed;pointer-events:none;background:#e8590c;color:#fff;font:12px/1.4 system-ui;padding:1px 6px;border-radius:3px;z-index:2147483647}
    .__uif-btn{position:fixed;right:16px;bottom:16px;z-index:2147483647;border:0;border-radius:20px;padding:8px 14px;font:14px system-ui;background:#1c7ed6;color:#fff;box-shadow:0 2px 8px #0004;cursor:pointer}
    .__uif-btn.on{background:#e8590c}
    .__uif-box{position:fixed;z-index:2147483647;background:#fff;color:#111;border:1px solid #ccc;border-radius:8px;padding:10px;width:320px;box-shadow:0 6px 24px #0003;font:13px system-ui}
    .__uif-box textarea{width:100%;height:80px;box-sizing:border-box;font:13px system-ui;margin:6px 0}
    .__uif-box button{margin-right:6px;padding:4px 10px;cursor:pointer}
    .__uif-pin{position:absolute;z-index:2147483645;width:20px;height:20px;border-radius:50%;color:#fff;font:bold 11px/20px system-ui;text-align:center;cursor:default;box-shadow:0 1px 4px #0006}
    .__uif-pin.open{background:#e8590c}.__uif-pin.done{background:#2f9e44}`;
  document.head.appendChild(css);
  const hl = Object.assign(document.createElement("div"), {className: "__uif-hl"});
  const tag = Object.assign(document.createElement("div"), {className: "__uif-tag"});
  const btn = Object.assign(document.createElement("button"), {className: "__uif-btn", textContent: "💬 UI"});
  btn.title = "Режим замечаний (или держите Alt и кликните по элементу)";
  let picking = false, box = null;
  const own = el => el.closest && el.closest(".__uif-btn,.__uif-box,.__uif-pin");
  const setPick = on => { picking = on; btn.classList.toggle("on", on); if (!on) { hl.remove(); tag.remove(); } };
  btn.onclick = e => { e.stopPropagation(); setPick(!picking); };
  document.body.appendChild(btn);

  function selector(el) {
    if (el.id && document.querySelectorAll("#" + CSS.escape(el.id)).length === 1) return "#" + CSS.escape(el.id);
    const tid = el.getAttribute("data-testid"); if (tid) return `[data-testid="${tid}"]`;
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.body && parts.length < 6; n = n.parentElement) {
      if (n.id) { parts.unshift("#" + CSS.escape(n.id)); break; }
      const same = [...(n.parentElement ? n.parentElement.children : [])].filter(c => c.tagName === n.tagName);
      parts.unshift(n.tagName.toLowerCase() + (same.length > 1 ? `:nth-of-type(${same.indexOf(n) + 1})` : ""));
    }
    return parts.join(" > ");
  }
  function show(el) {
    const r = el.getBoundingClientRect();
    Object.assign(hl.style, {left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px"});
    tag.textContent = selector(el);
    Object.assign(tag.style, {left: r.left + "px", top: Math.max(0, r.top - 20) + "px"});
    document.body.append(hl, tag);
  }
  document.addEventListener("mousemove", e => {
    if ((picking || e.altKey) && !box && !own(e.target)) show(e.target); else if (!picking) { hl.remove(); tag.remove(); }
  }, true);
  document.addEventListener("click", e => {
    if (!(picking || e.altKey) || box || own(e.target)) return;
    e.preventDefault(); e.stopPropagation(); ask(e.target, e.clientX, e.clientY);
  }, true);

  function ask(el, x, y) {
    box = document.createElement("div"); box.className = "__uif-box";
    box.innerHTML = `<b>Замечание к</b> <code></code><textarea placeholder="Что изменить?"></textarea>
      <button data-a="send">Отправить</button><button data-a="cancel">Отмена</button>`;
    box.querySelector("code").textContent = selector(el);
    Object.assign(box.style, {left: Math.min(x, innerWidth - 340) + "px", top: Math.min(y + 10, innerHeight - 170) + "px"});
    document.body.appendChild(box);
    const ta = box.querySelector("textarea"); ta.focus();
    const close = () => { box.remove(); box = null; setPick(false); };
    box.onclick = async e => {
      const a = e.target.dataset && e.target.dataset.a; if (!a) return;
      if (a === "cancel" || !ta.value.trim()) return close();
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      const payload = {
        path: location.pathname + location.search, selector: selector(el), comment: ta.value.trim(),
        text: (el.innerText || el.value || "").trim().slice(0, 80), html: el.outerHTML.slice(0, 300),
        rect: [Math.round(r.width), Math.round(r.height), Math.round(r.left + scrollX), Math.round(r.top + scrollY)],
        viewport: [innerWidth, innerHeight], styles: Object.fromEntries(STYLES.map(k => [k, cs.getPropertyValue(k)])),
      };
      const res = await fetch(API, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
      close(); if (res.ok) pins();
    };
    ta.onkeydown = e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) box.querySelector('[data-a="send"]').click(); if (e.key === "Escape") close(); };
  }
  async function pins() {
    document.querySelectorAll(".__uif-pin").forEach(p => p.remove());
    const items = await (await fetch(API)).json();
    for (const it of items) {
      if (it.path !== location.pathname + location.search) continue;
      let el = null; try { el = document.querySelector(it.selector); } catch (_) {}
      if (!el) continue;
      const r = el.getBoundingClientRect(), p = document.createElement("div");
      p.className = "__uif-pin " + (it.status === "done" ? "done" : "open");
      p.textContent = it.n; p.title = `UI-${it.n} (${it.status}): ${it.comment}`;
      Object.assign(p.style, {left: r.left + scrollX - 10 + "px", top: r.top + scrollY - 10 + "px"});
      document.body.appendChild(p);
    }
  }
  pins(); addEventListener("resize", pins);
})();
