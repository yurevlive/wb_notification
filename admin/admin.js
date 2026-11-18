const { h, render: renderDom, Fragment } = preact;
const html = htm.bind(h);
const { useState, useEffect, useCallback } = preactHooks;

let TOKEN = localStorage.getItem("admin_token") || "";
let notify = () => {};

function toast(msg, isErr) {
  notify(msg, !!isErr);
}

async function api(path, opts = {}) {
  const headers = Object.assign({ "X-Admin-Token": TOKEN }, opts.headers || {});
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  if (res.status === 401) {
    TOKEN = "";
    localStorage.removeItem("admin_token");
    throw new Error("unauthorized");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Ошибка " + res.status);
  return data;
}

const num = (v) => new Intl.NumberFormat("ru-RU").format(Number(v) || 0);
const fmtDate = (ts) =>
  ts
    ? new Date(ts * 1000).toLocaleString("ru-RU", {
        day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit",
      })
    : "—";
const ago = (ts) => {
  if (!ts) return "—";
  const d = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (d < 60) return "только что";
  if (d < 3600) return Math.floor(d / 60) + " мин назад";
  if (d < 86400) return Math.floor(d / 3600) + " ч назад";
  return Math.floor(d / 86400) + " дн назад";
};

function useRoute() {
  const read = () => {
    const raw = location.hash.replace(/^#\/?/, "");
    const [path, qs] = raw.split("?");
    return { parts: path.split("/").filter(Boolean), params: new URLSearchParams(qs || "") };
  };
  const [route, setRoute] = useState(read());
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

function Spark({ points, width = 160, height = 34 }) {
  const pts = (points || []).map(Number).filter((x) => x > 0);
  if (pts.length < 2) return html`<span class="muted">нет истории</span>`;
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = Math.max(1, hi - lo);
  const step = width / (pts.length - 1);
  const d = pts
    .map((p, i) => `${(i * step).toFixed(1)},${(height - ((p - lo) / span) * (height - 4) - 2).toFixed(1)}`)
    .join(" ");
  const up = pts[pts.length - 1] > pts[0];
  return html`<svg class="spark" width=${width} height=${height} viewBox="0 0 ${width} ${height}">
    <polyline fill="none" stroke=${up ? "#EF4444" : "#22C55E"} stroke-width="2" points=${d} />
  </svg>`;
}

function Login({ onDone }) {
  const [value, setValue] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const token = value.trim();
    if (!token) return;
    setBusy(true);
    setErr("");
    TOKEN = token;
    try {
      await api("/admin/api/health");
      localStorage.setItem("admin_token", token);
      onDone();
    } catch (ex) {
      TOKEN = "";
      setErr(ex.message === "unauthorized" ? "Токен не подошёл" : ex.message);
    } finally {
      setBusy(false);
    }
  };

  return html`<div class="wrap">
    <form class="card login" onSubmit=${submit}>
      <h1>WB.Track — администратор</h1>
      <div class="muted" style="margin-bottom:12px">Вставь ADMIN_TOKEN из .env на сервере</div>
      <input type="password" autocomplete="off" placeholder="ADMIN_TOKEN"
             value=${value} onInput=${(e) => setValue(e.target.value)} />
      <div class="row" style="margin-top:12px">
        <button class="primary" disabled=${busy}>${busy ? "Проверяю..." : "Войти"}</button>
      </div>
      <div class="err">${err}</div>
    </form>
  </div>`;
}

const NAV = [
  ["overview", "Обзор"],
  ["users", "Пользователи"],
  ["tasks", "Задачи"],
  ["contacts", "Контакты"],
  ["broadcast", "Рассылка"],
  ["logs", "Логи"],
  ["calc", "Калькулятор"],
];

function Layout({ route, onLogout, children }) {
  const active = route.parts[0] || "overview";
  return html`<div>
    <div class="top">
      <h1>WB.Track — администратор</h1>
      <div class="row tight">
        <span class="who">токен активен</span>
        <button class="ghost" onClick=${onLogout}>Выйти</button>
      </div>
    </div>
    <div class="wrap">
      <div class="nav">
        ${NAV.map(([key, label]) => html`<a key=${key} href=${"#/" + key} class=${key === active ? "active" : ""}>${label}</a>`)}
      </div>
      ${children}
    </div>
  </div>`;
}

function Overview() {
  const [health, setHealth] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [err, setErr] = useState("");
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const [h, t] = await Promise.all([api("/admin/api/health"), api("/admin/api/tasks")]);
      setHealth(h);
      setTasks(t);
      setErr("");
    } catch (ex) {
      setErr(ex.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async () => {
    setRunning(true);
    try {
      const r = await api("/admin/api/run", { method: "POST" });
      toast(r.message || (r.ok ? "Запуск отправлен" : r.error || "Не вышло"), !r.ok);
      if (r.url) window.open(r.url, "_blank");
    } catch (ex) {
      toast(ex.message, true);
    } finally {
      setRunning(false);
    }
  };

  if (!health) return html`<div class="card">${err ? "Ошибка: " + err : "Загрузка..."}</div>`;

  const byOwner = {};
  tasks.forEach((t) => { const o = t.owner || "default"; byOwner[o] = (byOwner[o] || 0) + 1; });
  const owners = Object.entries(byOwner).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...owners.map((x) => x[1]));
  const wl = health.worker_last;

  return html`<div>
    <div class="card">
      <div class="grid">
        <div class="stat"><b>${num(health.users)}</b><span>пользователей</span></div>
        <div class="stat"><b>${num(health.tasks)}</b><span>задач</span></div>
        <div class="stat"><b>${num(health.contacts)}</b><span>контактов TG</span></div>
        <div class="stat"><b>${num(health.worker_runs)}</b><span>прогонов воркера</span></div>
      </div>
    </div>

    <div class="card">
      <h2>Состояние</h2>
      <div class="kv">
        <b>Последняя проверка</b><span>${ago(health.last_check)} (${fmtDate(health.last_check)})</span>
        <b>Рантайм</b><span>
          <span class=${"tag " + (health.worker_token_set ? "ok" : "bad")}>WORKER_TOKEN</span>
          <span class=${"tag " + (health.admin_token_set ? "ok" : "bad")}>ADMIN_TOKEN</span>
          <span class=${"tag " + (health.tg_token_set ? "ok" : "bad")}>TG_TOKEN</span>
          <span class="tag">REQUIRE_TOKEN: ${String(health.require_token)}</span>
        </span>
        <b>Воркер</b><span>${wl ? `${ago(wl.ts)} · проверено ${num(wl.checked)}, алертов ${num(wl.alerts)}, ошибок ${num(wl.errors)}` : "логов нет"}</span>
      </div>
      <div class="row" style="margin-top:12px">
        <button class="primary" onClick=${run} disabled=${running}>${running ? "Запускаю..." : "Запустить проверку"}</button>
        <span class="muted">дергает GitHub Actions monitor.yml</span>
      </div>
    </div>

    <div class="card">
      <h2>Задачи по владельцам</h2>
      ${owners.length === 0
        ? html`<div class="muted">Задач нет</div>`
        : owners.map(([owner, count]) => html`<div class="row" style="margin:6px 0" key=${owner}>
            <a href=${"#/users/" + encodeURIComponent(owner)} style="width:160px;font-size:12px;overflow:hidden;text-overflow:ellipsis">${owner}</a>
            <div class="bar" style="flex:1"><i style=${"width:" + Math.round((count / max) * 100) + "%"}></i></div>
            <b style="font-size:12px;width:32px;text-align:right">${count}</b>
          </div>`)}
    </div>
  </div>`;
}

function Users() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api("/admin/api/users"));
      setErr("");
    } catch (ex) {
      setErr(ex.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const del = async (login) => {
    if (!confirm("Удалить " + login + " вместе с задачами?")) return;
    try {
      await api("/admin/api/users/" + encodeURIComponent(login), { method: "DELETE" });
      toast("Удалено");
      load();
    } catch (ex) { toast(ex.message, true); }
  };

  const resetPw = async (login) => {
    const pw = prompt("Новый пароль для " + login + ":");
    if (!pw) return;
    try {
      await api("/admin/api/users/" + encodeURIComponent(login) + "/reset_password", {
        method: "POST", body: JSON.stringify({ password: pw }),
      });
      toast("Пароль изменён, старая сессия сброшена");
    } catch (ex) { toast(ex.message, true); }
  };

  const needle = q.trim().toLowerCase();
  const view = rows.filter(
    (r) => !needle || r.login.toLowerCase().includes(needle) || String(r.tg_id).toLowerCase().includes(needle)
  );

  return html`<div class="card">
    <div class="row" style="margin-bottom:10px">
      <input placeholder="Поиск по логину или Telegram" value=${q} onInput=${(e) => setQ(e.target.value)} />
      <button class="ghost" onClick=${load}>Обновить</button>
    </div>
    ${err ? html`<div class="muted">Ошибка: ${err}</div>` : null}
    <table>
      <thead><tr>
        <th>Логин</th><th>Telegram</th><th class="hide-sm">Задач</th>
        <th class="hide-sm">Создан</th><th class="hide-sm">Был</th><th class="right">Действия</th>
      </tr></thead>
      <tbody>
      ${view.map((u) => html`<tr key=${u.login}>
        <td><a href=${"#/users/" + encodeURIComponent(u.login)}>${u.login}</a></td>
        <td>${u.tg_id || html`<span class="muted">—</span>`}</td>
        <td class="hide-sm">${u.tasks}</td>
        <td class="hide-sm">${fmtDate(u.created)}</td>
        <td class="hide-sm">${ago(u.last_seen)}</td>
        <td class="right">
          <button class="ghost" onClick=${() => resetPw(u.login)}>Сбросить пароль</button>
          <button class="danger" onClick=${() => del(u.login)}>Удалить</button>
        </td>
      </tr>`)}
      </tbody>
    </table>
    ${view.length === 0 ? html`<div class="muted" style="margin-top:10px">Ничего не найдено</div>` : null}
  </div>`;
}

function MessageBox({ login }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api("/admin/api/message", { method: "POST", body: JSON.stringify({ login, text }) });
      toast("Сообщение отправлено");
      setText("");
    } catch (ex) { toast(ex.message, true); } finally { setBusy(false); }
  };
  return html`<div style="margin-top:12px">
    <textarea placeholder="Сообщение в Telegram" value=${text} onInput=${(e) => setText(e.target.value)}></textarea>
    <div class="row" style="margin-top:8px">
      <button class="primary" onClick=${send} disabled=${busy || !text.trim()}>Отправить</button>
    </div>
  </div>`;
}

function UserCard({ login }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api("/admin/api/user/" + encodeURIComponent(login)));
      setErr("");
    } catch (ex) { setErr(ex.message); }
  }, [login]);

  useEffect(() => { load(); }, [load]);

  const patch = async (task, field, value) => {
    try {
      await api("/admin/api/tasks/" + encodeURIComponent(task.owner || "default") + "/" + task.sku, {
        method: "PATCH", body: JSON.stringify({ [field]: value }),
      });
      toast("Сохранено");
      load();
    } catch (ex) { toast(ex.message, true); }
  };

  const delTask = async (task) => {
    if (!confirm("Удалить задачу " + task.sku + "?")) return;
    try {
      await api("/admin/api/tasks/" + encodeURIComponent(task.owner || "default") + "/" + task.sku, { method: "DELETE" });
      toast("Удалено");
      load();
    } catch (ex) { toast(ex.message, true); }
  };

  if (err) return html`<div class="card">Ошибка: ${err}</div>`;
  if (!data) return html`<div class="card">Загрузка...</div>`;

  return html`<div>
    <div class="card">
      <div class="row">
        <h2 style="margin:0">${data.login}</h2>
        <a href="#/users" class="muted">← к списку</a>
      </div>
      <div class="kv" style="margin-top:12px">
        <b>Telegram</b><span>${data.tg_id || "—"} ${data.tg_raw && data.tg_raw !== data.tg_id ? " (" + data.tg_raw + ")" : ""}</span>
        <b>Создан</b><span>${fmtDate(data.created)}</span>
        <b>Последний вход</b><span>${ago(data.last_seen)}</span>
        <b>Задач</b><span>${data.tasks.length}</span>
      </div>
      ${data.tg_id ? html`<${MessageBox} login=${data.login} />` : html`<div class="muted" style="margin-top:10px">Telegram не привязан — написать нельзя</div>`}
    </div>

    <div class="card">
      <h2>Задачи</h2>
      ${data.tasks.length === 0 ? html`<div class="muted">Пусто</div>` : html`<table>
        <thead><tr><th>Артикул</th><th>СБП</th><th>Цель</th><th>Кол-во</th><th class="hide-sm">История</th><th></th></tr></thead>
        <tbody>
        ${data.tasks.map((t) => html`<tr key=${t.sku}>
          <td><a href=${"https://www.wildberries.ru/catalog/" + t.sku + "/detail.aspx"} target="_blank" rel="noopener">${t.sku}</a></td>
          <td>${t.current_sbp ? num(t.current_sbp) + " ₽" : "—"}</td>
          <td><input style="width:90px" type="number" value=${t.target_price}
                 onChange=${(e) => patch(t, "target_price", e.target.value)} /></td>
          <td><input style="width:70px" type="number" value=${t.limit}
                 onChange=${(e) => patch(t, "limit", e.target.value)} /></td>
          <td class="hide-sm"><${Spark} points=${t.history} /></td>
          <td class="right"><button class="danger" onClick=${() => delTask(t)}>Удалить</button></td>
        </tr>`)}
        </tbody></table>`}
    </div>
  </div>`;
}

function Tasks() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api("/admin/api/tasks"));
      setErr("");
    } catch (ex) { setErr(ex.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = async (task, field, value) => {
    try {
      await api("/admin/api/tasks/" + encodeURIComponent(task.owner || "default") + "/" + task.sku, {
        method: "PATCH", body: JSON.stringify({ [field]: value }),
      });
      toast("Сохранено");
      load();
    } catch (ex) { toast(ex.message, true); }
  };

  const del = async (task) => {
    if (!confirm("Удалить задачу?")) return;
    try {
      await api("/admin/api/tasks/" + encodeURIComponent(task.owner || "default") + "/" + task.sku, { method: "DELETE" });
      toast("Удалено");
      load();
    } catch (ex) { toast(ex.message, true); }
  };

  const needle = q.trim().toLowerCase();
  const view = rows.filter((t) =>
    !needle ||
    String(t.sku).includes(needle) ||
    (t.owner || "default").toLowerCase().includes(needle) ||
    (t.name || "").toLowerCase().includes(needle)
  );

  return html`<div class="card">
    <div class="row" style="margin-bottom:10px">
      <input placeholder="Поиск: владелец, артикул, название" value=${q} onInput=${(e) => setQ(e.target.value)} />
      <button class="ghost" onClick=${load}>Обновить</button>
    </div>
    ${err ? html`<div class="muted">Ошибка: ${err}</div>` : null}
    <table>
      <thead><tr>
        <th>Владелец</th><th>Артикул</th><th class="hide-sm">Товар</th><th>СБП</th><th>Цель</th><th>Кол-во</th><th></th>
      </tr></thead>
      <tbody>
      ${view.map((t) => html`<tr key=${(t.owner || "default") + ":" + t.sku}>
        <td><a href=${"#/users/" + encodeURIComponent(t.owner || "default")}>${t.owner || "default"}</a></td>
        <td><a href=${"https://www.wildberries.ru/catalog/" + t.sku + "/detail.aspx"} target="_blank" rel="noopener">${t.sku}</a></td>
        <td class="hide-sm" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.name || "—"}</td>
        <td>${t.current_sbp ? num(t.current_sbp) : "—"}</td>
        <td><input style="width:90px" type="number" value=${t.target_price} onChange=${(e) => patch(t, "target_price", e.target.value)} /></td>
        <td><input style="width:70px" type="number" value=${t.limit} onChange=${(e) => patch(t, "limit", e.target.value)} /></td>
        <td class="right"><button class="danger" onClick=${() => del(t)}>Удалить</button></td>
      </tr>`)}
      </tbody>
    </table>
    ${view.length === 0 ? html`<div class="muted" style="margin-top:10px">Ничего не найдено</div>` : null}
    <div class="muted" style="margin-top:8px">Изменения цены и количества сохраняются сразу после ввода.</div>
  </div>`;
}

function Contacts() {
  const [data, setData] = useState({});
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [target, setTarget] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api("/admin/api/contacts"));
      setErr("");
    } catch (ex) { setErr(ex.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const needle = q.trim().toLowerCase();
  const rows = Object.entries(data).filter(
    ([name, info]) => !needle || name.toLowerCase().includes(needle) || String(info.id).includes(needle)
  );

  return html`<div class="card">
    <div class="row" style="margin-bottom:10px">
      <input placeholder="Поиск по username или id" value=${q} onInput=${(e) => setQ(e.target.value)} />
      <button class="ghost" onClick=${load}>Обновить</button>
    </div>
    ${err ? html`<div class="muted">Ошибка: ${err}</div>` : null}
    <table>
      <thead><tr><th>Username</th><th>Имя</th><th>Chat id</th><th class="right"></th></tr></thead>
      <tbody>
      ${rows.map(([name, info]) => html`<tr key=${name}>
        <td>@${name}</td>
        <td>${info.name || "—"}</td>
        <td>${info.id}</td>
        <td class="right"><button class="ghost" onClick=${() => setTarget("@" + name)}>Написать</button></td>
      </tr>`)}
      </tbody>
    </table>
    ${rows.length === 0 ? html`<div class="muted" style="margin-top:10px">Контактов нет</div>` : null}
    ${target ? html`<div class="card" style="margin-top:14px;background:var(--card2)">
      <div class="row"><b>Сообщение ${target}</b><button class="ghost" onClick=${() => setTarget("")}>Отмена</button></div>
      <${MessageBox} login=${target} />
    </div>` : null}
  </div>`;
}

function Broadcast() {
  const [users, setUsers] = useState([]);
  const [history, setHistory] = useState([]);
  const [audience, setAudience] = useState("registered");
  const [picked, setPicked] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const [u, h] = await Promise.all([api("/admin/api/users"), api("/admin/api/broadcasts")]);
      setUsers(u);
      setHistory(h);
      setErr("");
    } catch (ex) { setErr(ex.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = (login) => {
    setPicked((prev) => (prev.includes(login) ? prev.filter((x) => x !== login) : prev.concat(login)));
  };

  const send = async () => {
    if (!text.trim()) return;
    if (audience === "logins" && picked.length === 0) { toast("Выбери хотя бы одного", true); return; }
    if (!confirm("Отправить " + text.length + " символов? Аудитория: " + audience)) return;
    setBusy(true);
    try {
      const r = await api("/admin/api/broadcast", {
        method: "POST",
        body: JSON.stringify({ text, audience, logins: picked }),
      });
      toast("Отправлено " + r.sent + " из " + r.total + (r.failed ? ", ошибок " + r.failed : ""));
      setText("");
      load();
    } catch (ex) { toast(ex.message, true); } finally { setBusy(false); }
  };

  return html`<div>
    <div class="card">
      <h2>Рассылка</h2>
      ${err ? html`<div class="muted">Ошибка: ${err}</div>` : null}
      <div class="row" style="margin-bottom:10px">
        <label class="row tight"><input type="radio" style="width:auto" checked=${audience === "registered"} onChange=${() => setAudience("registered")} /> зарегистрированные</label>
        <label class="row tight"><input type="radio" style="width:auto" checked=${audience === "all"} onChange=${() => setAudience("all")} /> все контакты бота</label>
        <label class="row tight"><input type="radio" style="width:auto" checked=${audience === "logins"} onChange=${() => setAudience("logins")} /> выбранные</label>
      </div>
      ${audience === "logins" ? html`<div class="card" style="background:var(--card2);max-height:220px;overflow:auto">
        ${users.map((u) => html`<label class="row tight" key=${u.login} style="margin:4px 0">
          <input type="checkbox" style="width:auto" checked=${picked.includes(u.login)} onChange=${() => toggle(u.login)} />
          <span>${u.login}</span> <span class="muted">${u.tg_id || "без TG"}</span>
        </label>`)}
      </div>` : null}
      <textarea placeholder="Текст сообщения" value=${text} onInput=${(e) => setText(e.target.value)}></textarea>
      <div class="row" style="margin-top:8px">
        <button class="primary" onClick=${send} disabled=${busy || !text.trim()}>${busy ? "Отправляю..." : "Отправить"}</button>
        <span class="muted">${text.length} символов</span>
      </div>
    </div>

    <div class="card">
      <h2>История</h2>
      ${history.length === 0 ? html`<div class="muted">Рассылок ещё не было</div>` : html`<table>
        <thead><tr><th>Когда</th><th>Аудитория</th><th>Текст</th><th>Итог</th></tr></thead>
        <tbody>
        ${history.slice().reverse().map((b, i) => html`<tr key=${i}>
          <td>${fmtDate(b.ts)}</td>
          <td>${b.audience}</td>
          <td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${b.text}</td>
          <td>${b.sent} / ${b.total}${b.failed ? " (ошибок " + b.failed + ")" : ""}</td>
        </tr>`)}
        </tbody></table>`}
    </div>
  </div>`;
}

function Logs() {
  const [rows, setRows] = useState([]);
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [auto, setAuto] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api("/admin/api/worker_logs"));
      setErr("");
    } catch (ex) { setErr(ex.message); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [auto, load]);

  const view = rows.slice().reverse().filter((x) => !onlyErrors || x.errors > 0);

  return html`<div class="card">
    <div class="row" style="margin-bottom:10px">
      <label class="row tight"><input type="checkbox" style="width:auto" checked=${onlyErrors} onChange=${(e) => setOnlyErrors(e.target.checked)} /> только с ошибками</label>
      <label class="row tight"><input type="checkbox" style="width:auto" checked=${auto} onChange=${(e) => setAuto(e.target.checked)} /> автообновление</label>
      <div class="spacer"></div>
      <button class="ghost" onClick=${load}>Обновить</button>
    </div>
    ${err ? html`<div class="muted">Ошибка: ${err}</div>` : null}
    <table>
      <thead><tr><th>Время</th><th>Проверено</th><th>Алертов</th><th>Ошибок</th><th>Сообщение</th></tr></thead>
      <tbody>
      ${view.map((x, i) => html`<tr key=${i}>
        <td>${fmtDate(x.ts)}</td>
        <td>${x.checked}</td>
        <td>${x.alerts}</td>
        <td>${x.errors ? html`<span class="tag bad">${x.errors}</span>` : "0"}</td>
        <td>${x.message}</td>
      </tr>`)}
      </tbody>
    </table>
    ${view.length === 0 ? html`<div class="muted" style="margin-top:10px">Логов нет</div>` : null}
  </div>`;
}

function Calc() {
  const [base, setBase] = useState("");
  const [wallet, setWallet] = useState("");
  const [sbp, setSbp] = useState("");
  const [expr, setExpr] = useState("");

  const recalc = (from) => {
    let b = NaN;
    if (from === "b") b = parseFloat(base);
    else if (from === "w") b = parseFloat(wallet) * 395 / 426;
    else if (from === "s") b = parseFloat(sbp) * 395 / 454;
    if (!isFinite(b) || b <= 0) return;
    const w = Math.round(b * 426 / 395);
    const s = Math.round(b * 454 / 395);
    setBase(String(Math.round(b)));
    setWallet(String(w));
    setSbp(String(s));
  };

  const evalExpr = () => {
    const clean = expr.replace(/[^0-9.+\-*/()]/g, "");
    if (!clean) return;
    try {
      const val = Function('"use strict";return (' + clean + ")")();
      setExpr(String(Math.round(Number(val) * 100) / 100));
    } catch (e) {
      setExpr("Ошибка");
    }
  };

  const press = (ch) => {
    if (ch === "C") { setExpr(""); return; }
    if (ch === "=") { evalExpr(); return; }
    setExpr((e) => e + ch);
  };

  const keys = ["7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "0", ".", "=", "+", "C"];

  return html`<div>
    <div class="card">
      <h2>Конвертер цен WB</h2>
      <div class="muted" style="margin-bottom:10px">
        База — цена из price-history. Кошелёк = база × 426/395, СБП = база × 454/395. Вводи любую — остальные посчитаются.
        Если у тебя на руках цена Озона, это не база WB — пересчёт не совпадёт.
      </div>
      <div class="calc-grid">
        <div><div class="muted">База, ₽</div><input type="number" value=${base} onInput=${(e) => { setBase(e.target.value); recalc("b"); }} /></div>
        <div><div class="muted">Кошелёк, ₽</div><input type="number" value=${wallet} onInput=${(e) => { setWallet(e.target.value); recalc("w"); }} /></div>
        <div><div class="muted">СБП, ₽</div><input type="number" value=${sbp} onInput=${(e) => { setSbp(e.target.value); recalc("s"); }} /></div>
      </div>
    </div>

    <div class="card">
      <h2>Калькулятор</h2>
      <div class="disp">${expr || "0"}</div>
      <div class="pad">
        ${keys.map((k) => html`<button key=${k} onClick=${() => press(k)}>${k}</button>`)}
      </div>
    </div>
  </div>`;
}

function App() {
  const route = useRoute();
  const [ready, setReady] = useState(!!TOKEN);
  const [msg, setMsg] = useState(null);

  notify = (text, isErr) => setMsg({ text, isErr, id: Date.now() });

  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 3200);
    return () => clearTimeout(t);
  }, [msg]);

  const logout = () => {
    TOKEN = "";
    localStorage.removeItem("admin_token");
    setReady(false);
    location.hash = "";
  };

  let screen;
  if (!ready) {
    screen = html`<${Login} onDone=${() => setReady(true)} />`;
  } else {
    const [head, param] = route.parts;
    const body =
      head === "users" && param ? html`<${UserCard} login=${decodeURIComponent(param)} />`
      : head === "users" ? html`<${Users} />`
      : head === "tasks" ? html`<${Tasks} />`
      : head === "contacts" ? html`<${Contacts} />`
      : head === "broadcast" ? html`<${Broadcast} />`
      : head === "logs" ? html`<${Logs} />`
      : head === "calc" ? html`<${Calc} />`
      : html`<${Overview} />`;
    screen = html`<${Layout} route=${route} onLogout=${logout}>${body}<//>`;
  }

  return html`<${Fragment}>
    ${screen}
    ${msg ? html`<div class=${"toast" + (msg.isErr ? " err" : "")}>${msg.text}</div>` : null}
  <//>`;
}

function mount() {
  if (!location.hash) location.hash = "#/overview";
  renderDom(html`<${App} />`, document.getElementById("app"));
}

mount();
