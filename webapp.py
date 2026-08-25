"""
webapp.py -- minimal local dashboard for the crawler.

Run:  pip install flask  &&  python webapp.py
Then open http://127.0.0.1:5000

Wraps the existing CLI pipeline: a form starts a crawl in a background
thread (one at a time), results are read straight from the SQLite DB and
the CSV/Excel export the crawl already produces.
"""

import os
import threading

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
)

import config
from crawler.seed_loader import load_seed_urls
from database.sqlite_manager import SQLiteManager
from main import run_phase_1_and_2_and_3, run_phase_4_and_5
from utils.checkpoint import Checkpoint
from utils.exporter import export_all

app = Flask(__name__)

# ponytail: single global "one crawl at a time" -- add a job queue only if
# you need concurrent crawls or restart-survival.
state = {"running": False, "error": None, "phase": "idle", "cancel": False}

EXTRACT_FLAGS = {
    "emails": "EXTRACT_EMAILS",
    "phones": "EXTRACT_PHONES",
    "images": "EXTRACT_IMAGES",
    "articles": "EXTRACT_ARTICLES",
    "products": "EXTRACT_PRODUCTS",
}


def run_crawl(seeds, extract, custom_prompt):
    state.update(running=True, error=None, cancel=False, phase="starting")
    for key, attr in EXTRACT_FLAGS.items():
        setattr(config, attr, key in extract)
    config.CUSTOM_PROMPT = custom_prompt
    try:
        db, cp = SQLiteManager(), Checkpoint()
        state["phase"] = "Phase 1-3: discovering profiles & websites"
        run_phase_1_and_2_and_3(seeds, db, cp)
        # ponytail: cancel only takes effect between phases -- the phase
        # functions don't check a flag mid-loop. Thread a callback through
        # main.py's ThreadPoolExecutor loops if you need instant cancel.
        if not state["cancel"]:
            state["phase"] = "Phase 4-5: crawling websites & extracting"
            run_phase_4_and_5(db, cp)
        if not state["cancel"]:
            state["phase"] = "exporting"
            export_all(db)
        state["phase"] = "cancelled" if state["cancel"] else "done"
    except Exception as e:  # surface any failure back to the page
        state["error"] = str(e)
        state["phase"] = "error"
    finally:
        state["running"] = False


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST" and not state["running"]:
        seeds = [s.strip() for s in request.form["seeds"].splitlines() if s.strip()]
        if not seeds:
            seeds = load_seed_urls()
        extract = request.form.getlist("extract")
        custom = request.form.get("custom_prompt", "").strip()
        threading.Thread(
            target=run_crawl, args=(seeds, extract, custom), daemon=True
        ).start()
        return redirect("/")

    q = request.args.get("q", "").strip().lower()
    rows = SQLiteManager().get_all_contacts()
    if q:
        rows = [
            r
            for r in rows
            if any(
                q in str(r.get(f, "")).lower()
                for f in ("website", "name", "organization", "emails", "phones")
            )
        ]
    return render_template_string(PAGE, rows=rows, state=state, flags=EXTRACT_FLAGS, q=q)


@app.route("/status")
def status():
    db = SQLiteManager()
    return jsonify(
        running=state["running"],
        phase=state["phase"],
        error=state["error"],
        websites=len(db.get_all_websites()),
        contacts=len(db.get_all_contacts()),
    )


@app.route("/cancel", methods=["POST"])
def cancel():
    state["cancel"] = True
    return ("", 204)


@app.route("/download/<name>")
def download(name):
    # only allow the known export filenames
    allowed = {
        "contacts.csv",
        "websites.csv",
        "discovered_urls.csv",
        "master_database.xlsx",
    }
    if name not in allowed:
        return "not found", 404
    return send_from_directory(os.path.abspath(config.OUTPUT_DIR), name, as_attachment=True)


PAGE = """
<!doctype html>
<html lang=en>
<head>
<meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Universal Crawler</title>
<style>
 :root{
   --bg:#0f1220; --panel:#171a2b; --panel2:#1e2236; --line:#2a2f47;
   --text:#e6e8f0; --muted:#9aa0b8; --accent:#6d5efc; --accent2:#22c55e;
   --danger:#ef4444; --radius:14px;
 }
 *{box-sizing:border-box}
 body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
   color:var(--text);background:
     radial-gradient(1200px 600px at 80% -10%,#2a2170 0,transparent 60%),
     radial-gradient(900px 500px at -10% 10%,#132a52 0,transparent 55%),var(--bg);
   min-height:100vh}
 .wrap{max-width:1080px;margin:0 auto;padding:2.2rem 1.2rem 4rem}
 header{display:flex;align-items:center;gap:.8rem;margin-bottom:1.6rem}
 .logo{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;
   background:linear-gradient(135deg,var(--accent),#a855f7);font-size:22px;
   box-shadow:0 8px 24px -8px var(--accent)}
 h1{font-size:1.35rem;margin:0;letter-spacing:-.02em}
 .sub{color:var(--muted);font-size:.85rem}
 .card{background:linear-gradient(180deg,var(--panel),var(--panel2));
   border:1px solid var(--line);border-radius:var(--radius);padding:1.3rem;
   box-shadow:0 12px 40px -18px #000;margin-bottom:1.3rem}
 .pill{display:inline-flex;align-items:center;gap:.5rem;padding:.45rem .9rem;
   border-radius:999px;font-size:.85rem;font-weight:600;border:1px solid var(--line);
   background:#0e1120}
 .dot{width:9px;height:9px;border-radius:50%;background:var(--muted)}
 .pill.run .dot{background:var(--accent);animation:pulse 1.1s infinite}
 .pill.done .dot{background:var(--accent2)} .pill.err .dot{background:var(--danger)}
 .pill.run{border-color:#3a3a8f} .pill.done{border-color:#1c5b34} .pill.err{border-color:#5b1c1c}
 @keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
 .stats{display:flex;gap:.7rem;margin-top:1rem;flex-wrap:wrap}
 .stat{flex:1;min-width:120px;background:#0e1120;border:1px solid var(--line);
   border-radius:10px;padding:.7rem .9rem}
 .stat b{font-size:1.5rem;display:block;letter-spacing:-.02em}
 .stat span{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
 label.fld{display:block;font-size:.8rem;color:var(--muted);margin:0 0 .4rem;
   text-transform:uppercase;letter-spacing:.05em}
 textarea,input[type=text]{width:100%;background:#0e1120;color:var(--text);
   border:1px solid var(--line);border-radius:10px;padding:.7rem .85rem;font:inherit;
   font-size:.9rem;resize:vertical}
 textarea{height:5.5rem;font-family:ui-monospace,Menlo,monospace}
 textarea:focus,input:focus{outline:none;border-color:var(--accent);
   box-shadow:0 0 0 3px #6d5efc33}
 .chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:.2rem 0 0}
 .chip{position:relative;cursor:pointer;user-select:none}
 .chip input{position:absolute;opacity:0}
 .chip span{display:inline-block;padding:.4rem .8rem;border-radius:999px;
   border:1px solid var(--line);background:#0e1120;font-size:.85rem;color:var(--muted);
   transition:.15s}
 .chip input:checked + span{background:#6d5efc22;border-color:var(--accent);color:#fff}
 .row{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}
 .row>div{flex:1;min-width:240px}
 .actions{display:flex;gap:.6rem;align-items:center}
 button{font:inherit;font-weight:600;cursor:pointer;border-radius:10px;
   padding:.6rem 1.2rem;border:1px solid var(--line);background:#0e1120;color:var(--text);
   transition:.15s}
 button:hover{border-color:#4a4f6f}
 button.primary{background:linear-gradient(135deg,var(--accent),#8b5cf6);border:none;
   box-shadow:0 8px 20px -10px var(--accent)}
 button.primary:hover{filter:brightness(1.1)}
 button:disabled{opacity:.4;cursor:not-allowed;filter:none}
 .bar{display:flex;justify-content:space-between;align-items:center;gap:1rem;
   flex-wrap:wrap;margin-bottom:.9rem}
 .bar h2{font-size:1.05rem;margin:0}
 .search{display:flex;gap:.5rem}
 .search input{width:230px}
 .dl a{color:var(--muted);text-decoration:none;font-size:.85rem;padding:.35rem .7rem;
   border:1px solid var(--line);border-radius:8px;margin-left:.4rem}
 .dl a:hover{color:#fff;border-color:var(--accent)}
 .twrap{overflow:auto;border:1px solid var(--line);border-radius:12px}
 table{border-collapse:collapse;width:100%;font-size:.85rem}
 th,td{padding:.6rem .8rem;text-align:left;border-bottom:1px solid var(--line);
   max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 th{position:sticky;top:0;background:#0e1120;color:var(--muted);font-size:.72rem;
   text-transform:uppercase;letter-spacing:.05em;z-index:1}
 tbody tr:hover{background:#ffffff08}
 td a{color:#8b9bff;text-decoration:none} td a:hover{text-decoration:underline}
 .empty{padding:2.5rem;text-align:center;color:var(--muted)}
 a.clear{color:var(--muted);font-size:.85rem;align-self:center}
</style>
</head>
<body>
<div class=wrap>
  <header>
    <div class=logo>🕸️</div>
    <div>
      <h1>Universal Crawler</h1>
      <div class=sub>Discovery &amp; public-contact extraction — local dashboard</div>
    </div>
    <div style="margin-left:auto" id=pill class=pill><i class=dot></i><span id=pilltxt>…</span></div>
  </header>

  <div class=card>
    <form method=post>
      <div class=row>
        <div>
          <label class=fld>Seed URLs <span style="text-transform:none">(one per line — blank uses configured SEED_FILE)</span></label>
          <textarea name=seeds placeholder="https://example-directory.com/listings"></textarea>
        </div>
      </div>
      <label class=fld>Extract</label>
      <div class=chips>
        {% for key in flags %}
          <label class=chip><input type=checkbox name=extract value="{{key}}"
            {% if key in ('emails','phones') %}checked{% endif %}><span>{{key}}</span></label>
        {% endfor %}
      </div>
      <div class=row style="margin-top:1rem">
        <div>
          <label class=fld>Custom LLM prompt <span style="text-transform:none">(optional — needs GEMINI_API_KEY)</span></label>
          <input type=text name=custom_prompt placeholder='e.g. "extract pricing tiers"'>
        </div>
      </div>
      <div class=actions>
        <button class=primary id=start type=submit>▶ Start crawl</button>
        <button type=button id=stop onclick="fetch('/cancel',{method:'POST'})">■ Stop</button>
      </div>
      <div class=stats id=stats style="display:none">
        <div class=stat><b id=s_web>0</b><span>Websites found</span></div>
        <div class=stat><b id=s_con>0</b><span>Contacts extracted</span></div>
      </div>
    </form>
  </div>

  <div class=card>
    <div class=bar>
      <h2>Results <span class=sub>({{ rows|length }})</span></h2>
      <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
        <form class=search method=get>
          <input type=text name=q value="{{q}}" placeholder="filter website / email / name">
          <button type=submit>Search</button>
          {% if q %}<a class=clear href="/">clear</a>{% endif %}
        </form>
        <span class=dl><a href="/download/contacts.csv">⬇ CSV</a><a href="/download/master_database.xlsx">⬇ Excel</a></span>
      </div>
    </div>
    {% if rows %}
    <div class=twrap>
      <table>
        <thead><tr><th>Website</th><th>Name</th><th>Organization</th><th>Emails</th><th>Phones</th></tr></thead>
        <tbody>
        {% for r in rows %}
          <tr>
            <td title="{{r.website}}">{% if r.website %}<a href="{{r.website}}" target=_blank rel=noopener>{{r.website}}</a>{% endif %}</td>
            <td title="{{r.name}}">{{r.name}}</td>
            <td title="{{r.organization}}">{{r.organization}}</td>
            <td title="{{r.emails}}">{{r.emails}}</td>
            <td title="{{r.phones}}">{{r.phones}}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
      <div class=empty>No contacts yet — start a crawl above{% if q %}, or clear the filter{% endif %}.</div>
    {% endif %}
  </div>
</div>

<script>
let wasRunning = false;
async function poll(){
  let s;
  try { s = await (await fetch('/status')).json(); } catch(e){ return; }
  const pill = document.getElementById('pill'), txt = document.getElementById('pilltxt');
  const stats = document.getElementById('stats');
  pill.className = 'pill';
  if (s.running){
    pill.classList.add('run'); txt.textContent = s.phase;
    stats.style.display = 'flex';
    document.getElementById('s_web').textContent = s.websites;
    document.getElementById('s_con').textContent = s.contacts;
  } else if (s.error){
    pill.classList.add('err'); txt.textContent = 'Error: ' + s.error;
  } else if (s.phase === 'done'){
    pill.classList.add('done'); txt.textContent = 'Done — ' + s.contacts + ' contacts';
  } else {
    txt.textContent = 'Idle';
  }
  document.getElementById('start').disabled = s.running;
  document.getElementById('stop').disabled = !s.running;
  if (wasRunning && !s.running) location.reload();  // refresh table when finished
  wasRunning = s.running;
}
poll(); setInterval(poll, 2000);
</script>
</body>
</html>
"""

def main():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False: the reloader restarts on file change and would kill
    # an in-flight crawl running in the background thread.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, use_reloader=False)


if __name__ == "__main__":
    main()
