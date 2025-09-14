import asyncio
import logging
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.store import load_config, save_config, load_admin, save_admin, verify_password
from app.config import Settings
from app.bot import BotManager

log = logging.getLogger("admin")


def html_base(body: str, title="Discord Media Bot — Admin") -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>{title}</title>
<style>
  /* Layout + base */
  *, *::before, *::after {{ box-sizing: border-box; }}
  :root {{
    --maxw: 980px;
    --gap: 12px;

    /* Dark palette */
    --bg: #0b0f1a;
    --panel: #0f172a;
    --panel-2: #111827;
    --text: #e5e7eb;
    --muted: #9ca3af;
    --border: rgba(148,163,184,0.18);
    --radius: 12px;

    /* Inputs */
    --input-bg: #0b1220;
    --input-bd: rgba(148,163,184,0.24);
    --input-focus: #6366f1;
    --accent: #6366f1;

    /* Buttons */
    --btn-bg: #4f46e5;
    --btn-bg-h: #4338ca;
    --btn-text: #fff;
    --btn-muted-bg: #1f2937;
    --btn-muted-bd: #374151;

    /* Badges */
    --ok-bg: #052e1b;
    --ok-bd: #064e3b;
    --ok-fg: #34d399;
    --err-bg: #3a0c0c;
    --err-bd: #7f1d1d;
    --err-fg: #f87171;
  }}

  body {{
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, sans-serif;
    max-width: var(--maxw);
    margin: 24px auto;
    padding: 0 12px;
    color: var(--text);
    background: radial-gradient(1200px 600px at 20% -10%, rgba(79,70,229,.12), transparent),
                radial-gradient(1000px 500px at 90% -20%, rgba(2,132,199,.12), transparent),
                var(--bg);
  }}

  h1 {{ font-size: 1.4rem; margin: 0 0 16px; font-weight: 700; }}
  h2 {{ font-size: 1.2rem; margin: 24px 0 8px; font-weight: 600; }}

  fieldset {{
    border: 1px solid var(--border);
    background: var(--panel);
    padding: 14px;
    border-radius: var(--radius);
    margin: 0 0 16px;
    overflow: hidden;
    box-shadow: 0 8px 30px rgba(0,0,0,.25);
  }}

  legend {{
    padding: 0 6px;
    font-weight: 600;
    color: var(--muted);
  }}

  label {{
    display: block;
    margin: 10px 0 6px;
    font-size: 0.95rem;
    color: var(--text);
  }}

  input, select {{
    width: 100%;
    max-width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--input-bd);
    border-radius: 10px;
    outline: none;
    color: var(--text);
    background: var(--input-bg);
    transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
    accent-color: var(--accent);
  }}

  input:focus, select:focus {{
    border-color: var(--input-focus);
    box-shadow: 0 0 0 3px rgba(99,102,241,.25);
    background: #0d1530;
  }}

  .row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--gap);
  }}

  .actions {{
    margin-top: 16px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}

  button {{
    padding: 10px 14px;
    border: 0;
    border-radius: 10px;
    background: var(--btn-bg);
    color: var(--btn-text);
    cursor: pointer;
    font-weight: 600;
    box-shadow: 0 6px 20px rgba(79,70,229,.35);
    transition: background .15s ease, transform .05s ease;
  }}
  button:hover {{ background: var(--btn-bg-h); }}
  button:active {{ transform: translateY(1px); }}

  a.btn {{
    padding: 10px 14px;
    border: 1px solid var(--btn-muted-bd);
    border-radius: 10px;
    text-decoration: none;
    color: var(--text);
    background: var(--btn-muted-bg);
  }}

  .muted {{ color: var(--muted); }}
  .badge {{ padding: 4px 10px; border-radius: 999px; font-weight: 700; letter-spacing:.2px; }}
  .badge-green {{ background: var(--ok-bg); color: var(--ok-fg); border: 1px solid var(--ok-bd); }}
  .badge-red   {{ background: var(--err-bg); color: var(--err-fg); border: 1px solid var(--err-bd); }}
  .right {{ float: right; }}

  .checkbox-block {{ margin: 10px 0 6px; }}
  .checkbox-block input[type="checkbox"] {{
    width: auto;
    display: inline-block;
    margin-top: 6px;
    transform: scale(1.1);
  }}

  /* Modal overlay */
  .modal-overlay {{
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    display: none;
    place-items: center;
    z-index: 1000;
  }}
  .modal {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    max-width: 420px;
    width: 90%;
    box-shadow: 0 10px 40px rgba(0,0,0,.6);
    text-align: center;
    animation: fadeIn .2s ease-out;
  }}
  .modal h3 {{ margin-top: 0; font-size: 1.1rem; margin-bottom: 12px; }}
  .modal p {{ margin: 0 0 16px; color: var(--muted); }}
  .modal button {{
    background: var(--btn-bg);
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    color: #fff;
    font-weight: 600;
    cursor: pointer;
  }}
  .modal.success h3 {{ color: #34d399; }}
  .modal.error h3   {{ color: #f87171; }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: scale(0.95); }}
    to {{ opacity: 1; transform: scale(1); }}
  }}
</style>
</head><body>
{body}
<div class="modal-overlay" id="modal">
  <div class="modal" id="modal-box">
    <h3 id="modal-title">Error</h3>
    <p id="modal-msg">Something went wrong</p>
    <button onclick="closeModal()">Close</button>
  </div>
</div>
<script>
function showModal(msg, title="Error") {{
  const box = document.getElementById("modal-box");
  box.classList.remove("success","error");
  if (title.toLowerCase() === "success") box.classList.add("success");
  else box.classList.add("error");
  document.getElementById("modal-title").innerText = title;
  document.getElementById("modal-msg").innerText = msg;
  document.getElementById("modal").style.display = "grid";
}}
function closeModal() {{ document.getElementById("modal").style.display = "none"; }}

async function saveConfig() {{
  const form = document.querySelector("form");
  const fd = new FormData(form);
  try {{
    const res = await fetch("/save", {{ method: "POST", body: fd }});
    let data = null;
    try {{ data = await res.json(); }} catch (_){{
    }}
    if (!res.ok) {{
      const msg = (data && (data.message || data.detail)) || "Save failed";
      showModal(msg, "Error");
      return;
    }}
    showModal((data && data.message) || "Settings saved and bot reloaded.", "Success");
  }} catch (err) {{
    showModal(String(err), "Error");
  }}
}}

async function restartBot() {{
  try {{
    const res = await fetch("/restart", {{ method: "POST" }});
    let data = null;
    try {{ data = await res.json(); }} catch (_){{
    }}
    if (!res.ok) {{
      const msg = (data && (data.message || data.detail)) || "Restart failed";
      showModal(msg, "Error");
      return;
    }}
    showModal((data && data.message) || "Bot restarted successfully.", "Success");
  }} catch (err) {{
    showModal(String(err), "Error");
  }}
}}
</script>
</body></html>""")


def build_app(bot: BotManager) -> FastAPI:
    admin = load_admin()
    secret_key = (admin or {}).get("secret_key", "dev-secret-change-me")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=secret_key, same_site="lax")

    def status_badge() -> str:
        st = (bot.status or "stopped").lower()
        if st == "running":
            return '<span class="badge badge-green">RUNNING</span>'
        return f'<span class="badge badge-red">{("ERROR" if st=="error" else "STOPPED")}</span>'

    # ---------- Setup ----------
    @app.get("/setup", response_class=HTMLResponse)
    def setup_page():
        if load_admin():
            return RedirectResponse("/", status_code=303)
        return html_base("""
<h1>Setup Admin Account</h1>
<form method="post" action="/setup">
  <fieldset>
    <label>Username</label>
    <input name="username" required/>
    <label>Password</label>
    <input name="password" type="password" required/>
  </fieldset>
  <div class="actions">
    <button type="submit">Create Account</button>
  </div>
</form>
""")

    @app.post("/setup")
    async def setup_submit(username: str = Form(...), password: str = Form(...)):
        if load_admin():
            return RedirectResponse("/", status_code=303)
        save_admin(username.strip(), password)
        return RedirectResponse("/login", status_code=303)

    # ---------- Auth ----------
    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        if not load_admin():
            return RedirectResponse("/setup", status_code=303)
        return html_base("""
<h1>Login</h1>
<form method="post" action="/login">
  <fieldset>
    <label>Username</label>
    <input name="username" required/>
    <label>Password</label>
    <input name="password" type="password" required/>
  </fieldset>
  <div class="actions">
    <button type="submit">Login</button>
  </div>
</form>
""")

    @app.post("/login")
    async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        admin = load_admin()
        if not admin:
            return RedirectResponse("/setup", status_code=303)
        if admin.get("username") == username.strip() and verify_password(admin, password):
            request.session["user"] = username.strip()
            return RedirectResponse("/", status_code=303)
        return RedirectResponse("/login", status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # ---------- Home ----------
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        if not load_admin():
            return RedirectResponse("/setup", status_code=303)
        if not request.session.get("user"):
            return RedirectResponse("/login", status_code=303)

        cfg = load_config()
        return html_base(f"""
<h1>Discord Media Bot — Admin <span class="right">{status_badge()}</span></h1>
<form method="post" action="/save">
  <fieldset>
    <legend>General</legend>
    <label>Bot Token</label>
    <input name="general.bot_token" type="password" value="{cfg.general.bot_token or ''}"/>
    <div class="row">
      <div>
        <label>Timezone</label>
        <input name="general.timezone" value="{cfg.general.timezone}"/>
      </div>
      <div>
        <label>Message ID File</label>
        <input name="general.message_id_file" value="{cfg.general.message_id_file or ''}"/>
      </div>
    </div>
    <div class="row">
      <div>
        <label>CA Cert Path</label>
        <input name="general.ca_cert_path" value="{cfg.general.ca_cert_path or ''}" placeholder=""/>
      </div>
      <div>
        <label> Allow insecure (disable SSL verification) </label>
        <div class="checkbox-block">
          <input name="general.insecure_ssl" type="checkbox" {'checked' if cfg.general.insecure_ssl else ''}>
        </div>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Tautulli (required)</legend>
    <div class="row">
      <div>
        <label>Base URL</label>
        <input name="tautulli_url" value="{cfg.tautulli_url or ''}" placeholder="http://tautulli:8181"
               {'required' if cfg.streams.channel_id else ''}/>
      </div>
      <div>
        <label>API Key</label>
        <input name="tautulli_api_key" type="password" value="{cfg.tautulli_api_key or ''}"
               {'required' if cfg.streams.channel_id else ''}/>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Plex Streams</legend>
    <div class="row">
      <div>
        <label>Channel ID</label>
        <input name="streams.channel_id" type="number" value="{cfg.streams.channel_id or ''}"/>
      </div>
      <div>
        <label>Streams Update (s)</label>
        <input name="general.update_seconds" type="number" value="{cfg.general.update_seconds}"/>
      </div>
    </div>
    <label>Post thumbnails</label>
    <div class="checkbox-block">
      <input name="streams.post_thumbnails" type="checkbox" {'checked' if cfg.streams.post_thumbnails else ''}>
    </div>
  </fieldset>

  <fieldset>
    <legend>Plex Status Channels (optional)</legend>
    <div class="row">
      <div>
        <label>Movies Channel ID</label>
        <input name="plex_channels.movies_channel" type="number"
               value="{cfg.plex_channels.movies_channel or ''}" placeholder="Leave empty to disable"/>
      </div>
      <div>
        <label>TV Shows Channel ID</label>
        <input name="plex_channels.tv_shows_channel" type="number"
               value="{cfg.plex_channels.tv_shows_channel or ''}" placeholder="Leave empty to disable"/>
      </div>
    </div>
    <div class="row">
      <div>
        <label>User Count Channel ID</label>
        <input name="plex_channels.user_count_channel" type="number"
               value="{cfg.plex_channels.user_count_channel or ''}" placeholder="Leave empty to disable"/>
      </div>
      <div>
        <label>Plex Status Update (s)</label>
        <input name="general.plex_update_seconds" type="number" value="{cfg.general.plex_update_seconds}"/>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>Statistics</legend>
    <div class="row">
      <div>
        <label>Channel ID</label>
        <input name="stats.channel_id" type="number" value="{cfg.stats.channel_id or ''}"/>
      </div>
      <div>
        <label>Stats Update (s)</label>
        <input name="general.stats_update_seconds" type="number" value="{cfg.general.stats_update_seconds}"/>
      </div>
    </div>
  </fieldset>


  <fieldset>
    <legend>Sonarr / Radarr (optional)</legend>
    <div class="row">
      <div>
        <label>Radarr URL</label>
        <input name="arr.radarr_host" value="{cfg.arr.radarr_host or ''}" placeholder="http://radarr:7878"/>
      </div>
      <div>
        <label>Radarr API Key</label>
        <input name="arr.radarr_api_key" type="password" value="{cfg.arr.radarr_api_key or ''}"/>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Sonarr URL</label>
        <input name="arr.sonarr_host" value="{cfg.arr.sonarr_host or ''}" placeholder="http://sonarr:8989"/>
      </div>
      <div>
        <label>Sonarr API Key</label>
        <input name="arr.sonarr_api_key" type="password" value="{cfg.arr.sonarr_api_key or ''}"/>
      </div>
    </div>
  </fieldset>

  <fieldset>
    <legend>qBittorrent (optional)</legend>
    <div class="row">
      <div>
        <label>Host URL</label>
        <input name="qbit.host" value="{cfg.qbit.host or ''}" placeholder="http://qbittorrent:8080"
               {'required' if cfg.qbit.channel_id else ''}/>
      </div>
      <div>
        <label>Username</label>
        <input name="qbit.username" value="{cfg.qbit.username or ''}"
               {'required' if cfg.qbit.channel_id else ''}/>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Password</label>
        <input name="qbit.password" type="password" value="{cfg.qbit.password or ''}"
               {'required' if cfg.qbit.channel_id else ''}/>
      </div>
      <div>
        <label>Channel ID</label>
        <input name="qbit.channel_id" type="number" value="{cfg.qbit.channel_id or ''}" placeholder="Leave empty to disable"/>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Downloads Update (s)</label>
        <input name="general.qb_update_seconds" type="number" value="{cfg.general.qb_update_seconds}"/>
      </div>
    </div>
  </fieldset>

  <div class="actions">
    <button type="button" onclick="saveConfig()">Save & Reload</button>
    <button type="button" onclick="restartBot()">Restart Bot</button>
    <a class="btn" href="/logout">Logout</a>
  </div>
</form>
""")

    # ---------- Helpers ----------
    def _get_bool(form, key: str) -> bool:
        # checkbox is present only when checked
        return form.get(key) in ("on", "true", "1")

    # ---------- Actions ----------
    @app.post("/save")
    async def save(request: Request):
        if not request.session.get("user"):
            return JSONResponse({"title": "Error", "message": "Not logged in", "type": "error"}, status_code=401)
    
        form = dict(await request.form())
        cfg = load_config()
    
        # --- update config first ---
        cfg.general.bot_token = form.get("general.bot_token", "").strip()
        cfg.general.timezone = (form.get("general.timezone", cfg.general.timezone) or "Europe/Stockholm").strip()
        cfg.general.message_id_file = form.get("general.message_id_file", cfg.general.message_id_file).strip()

        cfg.general.update_seconds = int(form.get("general.update_seconds", cfg.general.update_seconds) or 60)
        cfg.general.stats_update_seconds = int(form.get("general.stats_update_seconds", cfg.general.stats_update_seconds) or 86400)
        cfg.general.qb_update_seconds = int(form.get("general.qb_update_seconds", cfg.general.qb_update_seconds) or 120)
        cfg.general.plex_update_seconds = int(form.get("general.plex_update_seconds", cfg.general.plex_update_seconds) or 3600)
        cfg.general.ca_cert_path = form.get("general.ca_cert_path", "").strip() or None
        cfg.general.insecure_ssl = form.get("general.insecure_ssl") in ("on", "true", "1")

    
        ch = form.get("streams.channel_id", "").strip()
        cfg.streams.channel_id = int(ch) if ch else None
        # checkbox present only when checked, but fetch/FormData includes it; keep your helper:
        def _get_bool_local(k: str) -> bool:
            return form.get(k) in ("on", "true", "1")
        cfg.streams.post_thumbnails = _get_bool_local("streams.post_thumbnails")

        cfg.plex_channels.movies_channel = int(form.get("plex_channels.movies_channel", "") or 0) or None
        cfg.plex_channels.tv_shows_channel = int(form.get("plex_channels.tv_shows_channel", "") or 0) or None
        cfg.plex_channels.user_count_channel = int(form.get("plex_channels.user_count_channel", "") or 0) or None
    
        sch = form.get("stats.channel_id", "").strip()
        cfg.stats.channel_id = int(sch) if sch else None
    
        cfg.tautulli_url = form.get("tautulli_url", "").strip()
        cfg.tautulli_api_key = form.get("tautulli_api_key", "").strip()
    
        cfg.arr.radarr_host = form.get("arr.radarr_host", "").strip() or None
        cfg.arr.radarr_api_key = form.get("arr.radarr_api_key", "").strip() or None
        cfg.arr.sonarr_host = form.get("arr.sonarr_host", "").strip() or None
        cfg.arr.sonarr_api_key = form.get("arr.sonarr_api_key", "").strip() or None
    
        cfg.qbit.host = form.get("qbit.host", "").strip() or None
        cfg.qbit.username = form.get("qbit.username", "").strip() or None
        cfg.qbit.password = form.get("qbit.password", "").strip() or None
        qch = form.get("qbit.channel_id", "").strip()
        cfg.qbit.channel_id = int(qch) if qch else None
    
        # --- validate after update ---
        if cfg.streams.channel_id and (not cfg.tautulli_url or not cfg.tautulli_api_key):
            return JSONResponse(
                {"title": "Error", "message": "Tautulli URL and API Key are required when Plex Streams is enabled.", "type": "error"},
                status_code=400
            )
        if cfg.qbit.channel_id and (not cfg.qbit.host or not cfg.qbit.username or not cfg.qbit.password):
            return JSONResponse(
                {"title": "Error", "message": "qBittorrent host/username/password are required when Downloads is enabled.", "type": "error"},
                status_code=400
            )
    
        save_config(cfg)
        try:
            await bot.reload(cfg)
        except asyncio.CancelledError:
            pass
    
        return JSONResponse({"title": "Success", "message": "Settings saved and bot reloaded.", "type": "success"})

    @app.post("/restart")
    async def restart(request: Request):
        # Optional check: only allow logged-in users
        if not request.session.get("user"):
            return JSONResponse({"title": "Error", "message": "Not logged in", "type": "error"}, status_code=401)
        try:
            cfg = load_config()
            if not cfg.general.bot_token:
                return JSONResponse({"title": "Error", "message": "Bot token missing. Set it in settings first.", "type": "error"}, status_code=400)
            await bot.reload(cfg)
            return JSONResponse({"title": "Success", "message": "Bot restarted successfully.", "type": "success"})
        except RuntimeError as e:
            return JSONResponse({"title": "Error", "message": str(e), "type": "error"}, status_code=400)
        except Exception as e:
            log.exception("Restart failed")
            return JSONResponse({"title": "Error", "message": f"Unexpected error: {e}", "type": "error"}, status_code=500)

    return app

