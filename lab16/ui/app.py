import os

import requests
import streamlit as st

API = os.environ.get("API_URL", "http://localhost:8000")
st.set_page_config(page_title="Domain Knowledge Hub", layout="wide")
st.title("Domain Knowledge Hub · Прогнозування енергоспоживання")
st.caption("Відповіді й рекомендації формує система ШІ (локальна модель qwen2.5:7b); перевіряйте джерела.")
tab1, tab2, tab3 = st.tabs(["Рекомендації", "Новий користувач", "Запитати агента"])

with tab1:
    users = requests.get(f"{API}/users", timeout=120).json()
    labels = {f"{u['user_id']} · {u['role']} · {u['group']}" + (" · новий" if u["cold"] else ""): u["user_id"] for u in users}
    c1, c2, c3 = st.columns(3)
    who = c1.selectbox("Користувач", list(labels))
    method = c2.selectbox("Метод", ["hybrid", "graph", "embedding", "popularity"])
    role = c3.selectbox("Роль (перевизначити)", ["(як у профілі)", "external", "analyst", "dispatcher", "head"])
    c4, c5 = st.columns(2)
    verified = c4.checkbox("Лише перевірені (verified)", value=True)
    fresh = c5.number_input("Свіжість, днів (0 — без обмеження)", 0, 120, 0)
    if st.button("Рекомендувати"):
        p = {"user_id": labels[who], "method": method, "k": 5, "verified_only": verified, "with_explanations": True}
        if role != "(як у профілі)":
            p["role"] = role
        if fresh:
            p["max_age_days"] = fresh
        r = requests.get(f"{API}/recommend", params=p, timeout=600).json()
        st.write(f"Відфільтровано: {r['filtered_out']}" + (" · холодний старт" if r["cold_start"] else ""))
        for it in r["items"]:
            with st.container(border=True):
                st.markdown(f"**{it['title']} › {it['section']}**  `{it['id']}` · {it['sensitivity']} · {it['date']}")
                if it.get("snippet"):
                    st.write(it["snippet"] + "…")
                st.info(it.get("explanation", ""))

with tab2:
    role = st.selectbox("Роль нового користувача", ["dispatcher", "analyst", "engineer"])
    group = st.text_input("Зона / напрям", {"dispatcher": "Dispatcher_2", "analyst": "forecasting", "engineer": "ami"}[role])
    if st.button("Підібрати стартові матеріали"):
        r = requests.post(f"{API}/recommend/cold", json={"role": role, "group": group, "k": 5}, timeout=600).json()
        for it in r["items"]:
            st.markdown(f"**{it['title']} › {it['section']}** `{it['id']}`")
            st.info(it["explanation"])

with tab3:
    q = st.text_input("Питання", "Які підстанції зараз перевантажені?")
    if st.button("Запитати"):
        with st.spinner("Агент збирає докази (локальна модель, до кількох хвилин)…"):
            r = requests.post(f"{API}/ask", json={"question": q}, timeout=900).json()
        st.write(r["answer"])
        st.caption(f"Інструменти: {r['tools']} · цитати: {r['citations']} · заблоковано: {r['blocked']} · {r['totals']}")
