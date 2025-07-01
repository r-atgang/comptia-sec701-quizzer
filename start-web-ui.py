import streamlit as st
import json, re
from datetime import datetime
from pathlib import Path
import pandas as pd
import altair as alt

# ---------------- Streamlit page ----------------
st.set_page_config(page_title="CompTIA Sec+ 701 Quizzer", layout="wide")

# ---------------- Paths ----------------
QUIZ_DIR  = Path("quiz-generated")
STUDY_DIR = Path("questions-to-study")
LOG_DIR   = Path("grade-logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

STATS_F   = LOG_DIR / "question_stats.json"
SUM_F     = LOG_DIR / "grade_summary.json"
for d in (QUIZ_DIR, STUDY_DIR):
    d.mkdir(parents=True, exist_ok=True)
if not STATS_F.exists(): STATS_F.write_text("{}")
if not SUM_F.exists():   SUM_F.write_text("[]")

# ---------------- Session state ----------------
st.session_state.setdefault("page","quiz")          # quiz | stats
st.session_state.setdefault("active",None)
st.session_state.setdefault("responses",[])
st.session_state.setdefault("show_results",False)
st.session_state.setdefault("result",{})
st.session_state.setdefault("confirm_delete",False)

# ---------------- Sidebar navigation ----------------
st.sidebar.title("Navigation")
if st.session_state.page=="quiz":
    if st.sidebar.button("📊 View Stats"):
        st.session_state.page="stats"; st.rerun()
else:
    if st.sidebar.button("← Back to Quiz"):
        st.session_state.page="quiz"; st.rerun()

# ---------------- Helper funcs (same as before) ----------------
def parse_quiz_file(path: Path):
    txt=path.read_text(encoding="utf-8")
    out=[]
    for blk in txt.split("[[Q]]")[1:]:
        q, rest=blk.split("[[/Q]]",1)
        answers=[a.strip() for a in re.findall(r"\[\[A\]\](.*?)\[\[/A\]\]",rest,re.S)]
        corr=re.search(r"\[\[C\]\](.*?)\[\[/C\]\]",rest,re.S).group(1).strip()
        if corr not in answers: answers.append(corr)
        out.append({"question":q.strip(),"answers":answers,"correct":corr})
    return out

def load_quizzes():
    q={}
    for p in list(QUIZ_DIR.glob("*.txt"))+list(STUDY_DIR.glob("*.txt")):
        n=p.stem; is_iter="_iter" in n
        base=n.split("_iter")[0] if is_iter else n
        it=int(n.split("_iter")[-1])+1 if is_iter else 1
        q[n]={"name":n,"base":base,"iter":it,"is_iter":is_iter,"path":p}
    return q

def log_attempt(quiz,score,corr,tot,qs,ua):
    # summary file
    g=json.loads(SUM_F.read_text())
    g.append({"quiz":quiz,"timestamp":datetime.now().isoformat(timespec='seconds'),
              "score":score,"correct":corr,"total":tot})
    SUM_F.write_text(json.dumps(g,indent=2))
    # question stats
    stats=json.loads(STATS_F.read_text())
    for q,a in zip(qs,ua):
        k=q["question"]
        stats.setdefault(k,{"attempts":0,"correct":0,"source":quiz.split("_iter")[0]})
        stats[k]["attempts"]+=1; 
        if a==q["correct"]: stats[k]["correct"]+=1
    STATS_F.write_text(json.dumps(stats,indent=2))

def create_iteration(base,missed):
    n=1
    while (STUDY_DIR/f"{base}_iter{n}.txt").exists(): n+=1
    p=STUDY_DIR/f"{base}_iter{n}.txt"
    with p.open("w",encoding="utf-8") as f:
        for q in missed:
            f.write(f"[[Q]] {q['question']} [[/Q]]\n")
            for a in q["answers"]: f.write(f"[[A]] {a} [[/A]]\n")
            f.write(f"[[C]] {q['correct']} [[/C]]\n\n")
    return p.stem

def delete_history(base,qmap):
    # remove stats & summary lines
    stats={k:v for k,v in json.loads(STATS_F.read_text()).items() if v["source"]!=base}
    STATS_F.write_text(json.dumps(stats,indent=2))
    summ=[e for e in json.loads(SUM_F.read_text()) if not e["quiz"].startswith(base)]
    SUM_F.write_text(json.dumps(summ,indent=2))
    for m in qmap.values():
        if m["base"]==base and m["is_iter"]: m["path"].unlink(missing_ok=True)

# ============ PAGE: STATS ============
if st.session_state.page=="stats":
    st.header("📊 Question Accuracy Heat-map")
    stats=json.loads(STATS_F.read_text())
    if not stats:
        st.info("No stats yet. Complete quizzes to generate data.")
    else:
        df=pd.DataFrame(
            {"question":k,
             "attempts":v["attempts"],
             "correct":v["correct"],
             "accuracy":v["correct"]/v["attempts"] if v["attempts"] else 0}
            for k,v in stats.items())
        df=df.sort_values("accuracy")
        heat = alt.Chart(df).mark_rect().encode(
            x=alt.X("accuracy:Q",bin=alt.Bin(maxbins=20),title="Accuracy"),
            y=alt.Y("question:N",sort="-x",title="Question"),
            color=alt.Color("accuracy:Q",scale=alt.Scale(scheme="redyellowgreen")),
            tooltip=["question:N","attempts:Q","correct:Q",alt.Tooltip("accuracy:Q",format=".1%")]
        ).configure_view(fill="transparent")
        st.altair_chart(heat,use_container_width=True)
    st.stop()  # skip quiz code when on stats page

# ============ PAGE: QUIZ ============
quizzes=load_quizzes()
bases=sorted({m["base"] for m in quizzes.values()})
base=st.sidebar.selectbox("Quiz",bases,disabled=st.session_state.confirm_delete)
attempts=sorted([m for m in quizzes.values() if m["base"]==base],key=lambda x:x["iter"])
latest=attempts[-1] if attempts else None

st.sidebar.subheader("Attempts")
summary=json.loads(SUM_F.read_text())
for meta in attempts:
    logs=[e for e in summary if e["quiz"]==meta["name"]]
    label=f"Attempt {meta['iter']}: "
    label+=f"{logs[-1]['score']}% ({logs[-1]['correct']}/{logs[-1]['total']})" if logs else "Not taken"
    st.sidebar.write(label)

if latest and st.sidebar.button("▶️ Take Quiz"):
    st.session_state.active=latest["name"]; st.session_state.responses=[]; st.session_state.show_results=False

# delete history
st.sidebar.markdown("---")
if st.sidebar.button("🗑 Delete History"): st.session_state.confirm_delete=True
if st.session_state.confirm_delete:
    st.sidebar.warning("Delete all attempts for this quiz?")
    c1,c2=st.sidebar.columns(2)
    if c1.button("Yes"): delete_history(base,quizzes); st.session_state.confirm_delete=False; st.rerun()
    if c2.button("Cancel"): st.session_state.confirm_delete=False

# show quiz
active=st.session_state.active
if active:
    meta=quizzes[active]; qs=parse_quiz_file(meta["path"])
    st.header(f"🛡️ CompTIA Sec+ 701 Quizzer – {meta['name']}")
    if not st.session_state.responses: st.session_state.responses=[None]*len(qs)

    with st.form("quizform"):
        for i,q in enumerate(qs):
            st.markdown(f"<div class='question-text'>{q['question']}</div>",unsafe_allow_html=True)
            sel=st.radio("options",q["answers"],index=None,
                         key=f"q{i}",label_visibility="collapsed")
            st.session_state.responses[i]=sel
        submitted=st.form_submit_button("Submit")

    if submitted:
        if None in st.session_state.responses:
            st.error("Answer all questions.")
        else:
            ua=st.session_state.responses
            corr=sum(u==q["correct"] for u,q in zip(ua,qs))
            pct=int(round(corr/len(qs)*100))
            log_attempt(active,pct,corr,len(qs),qs,ua)
            st.session_state.result={"pct":pct,"correct":corr,"total":len(qs),
                                     "qs":qs,"ua":ua}
            st.session_state.show_results=True
            st.session_state.responses=[]
            st.session_state.active=None
            if pct==100:
                delete_history(meta["base"],quizzes)
            else:
                create_iteration(meta["base"],
                    [q for u,q in zip(ua,qs) if u!=q["correct"]])
            st.rerun()

# results
if st.session_state.show_results:
    r=st.session_state.result
    st.subheader("Results")
    st.success(f"{r['pct']}% – {r['correct']}/{r['total']} correct")
    for u,q in zip(r["ua"],r["qs"]):
        if u==q["correct"]:
            st.write(f"✅ {q['question']}"); st.caption(f"Your answer: {u}")
        else:
            st.write(f"❌ {q['question']}"); st.caption(f"Your answer: {u} | Correct: {q['correct']}")
else:
    st.info("Select a quiz and press **Take Quiz**.")
