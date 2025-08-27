# tasks_code.py
# Team Task Tracker App (Streamlit) - Full Version with Password + Master Fixes

import os
import json
from datetime import date
from typing import List, Dict

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Team Task Tracker", layout="wide")

# --- Simple password gate ---
def check_password():
    if st.session_state.get("authed", False):
        return True
    pw = st.text_input("Password", type="password", placeholder="Enter password to continue")
    if pw:
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()

check_password()
# --- end password gate ---

HERE = os.path.abspath(os.path.dirname(__file__))
DATA_FILE = os.path.join(HERE, "tasks.csv")
MASTERS_FILE = os.path.join(HERE, "masters.json")

COLUMNS = [
    "Category",
    "Task Name",
    "Person",
    "Status",
    "Assigned Date",
    "ETA",
    "Date of Completion",
    "Notes/Issues",
]

DEFAULT_STATUSES = ["Pending", "In Progress", "Completed", "Not Live", "Live"]

# --------------------------- Master data helpers ---------------------------
def _contains_ci(items, value):
    """Case- and space-insensitive membership check."""
    v = str(value).strip().casefold()
    return any(str(x).strip().casefold() == v for x in items)

def load_masters() -> Dict[str, List[str]]:
    if os.path.exists(MASTERS_FILE):
        try:
            with open(MASTERS_FILE, "r", encoding="utf-8") as f:
                j = json.load(f)
            return {
                "Category": sorted(set(map(str, j.get("Category", [])))),
                "Person":   sorted(set(map(str, j.get("Person", [])))),
                "Status":   sorted(set(map(str, j.get("Status", DEFAULT_STATUSES)))),
            }
        except Exception:
            pass
    return {"Category": [], "Person": [], "Status": DEFAULT_STATUSES.copy()}

def save_masters(m: Dict[str, List[str]]) -> None:
    def _dedupe_ci(values):
        seen = {}
        for s in values:
            t = str(s).strip()
            if not t:
                continue
            k = t.casefold()
            if k not in seen:
                seen[k] = t
        return sorted(seen.values())

    cleaned = {
        "Category": _dedupe_ci(m.get("Category", [])),
        "Person":   _dedupe_ci(m.get("Person", [])),
        "Status":   _dedupe_ci(m.get("Status", [])),
    }
    with open(MASTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

def ensure_session_state():
    if "masters" not in st.session_state:
        st.session_state["masters"] = load_masters()
    if "tasks" not in st.session_state:
        st.session_state["tasks"] = load_data()

# --------------------------- Data I/O ---------------------------
def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df()
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNS].copy()
    for c in ["Category", "Task Name", "Person", "Status", "Notes/Issues"]:
        s = df[c].astype(str)
        s = s.str.replace("\u00A0", " ", regex=False)   # NBSP → space
        s = s.str.replace(r"\s+", " ", regex=True)     # collapse spaces
        df[c] = s.replace({"nan": "", "None": ""}).str.strip()
    for c in ["Assigned Date", "ETA", "Date of Completion"]:
        s = pd.to_datetime(df[c], errors="coerce")
        df[c] = s.dt.strftime("%Y-%m-%d").fillna("")
    return df

def load_data(path: str = DATA_FILE) -> pd.DataFrame:
    if os.path.exists(path):
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
            try:
                return normalize(pd.read_csv(path, encoding=enc))
            except Exception:
                continue
    return empty_df()

def save_data(df: pd.DataFrame, path: str = DATA_FILE) -> None:
    normalize(df).to_csv(path, index=False, encoding="utf-8")

def read_csv_flexible(uploaded_file) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=enc)
        except UnicodeDecodeError:
            continue
    uploaded_file.seek(0)
    return pd.read_csv(uploaded_file, encoding="latin1", on_bad_lines="skip")

# --------------------------- App state ---------------------------
ensure_session_state()
df_all = st.session_state["tasks"]

# --------------------------- Sidebar Filters ---------------------------
st.sidebar.header("Filters")
people_opts = sorted(df_all["Person"].dropna().unique())
cat_opts    = sorted(df_all["Category"].dropna().unique())
status_opts = sorted(df_all["Status"].dropna().unique())

f_person   = st.sidebar.multiselect("Person",   people_opts, key="fil_person")
f_category = st.sidebar.multiselect("Category", cat_opts,    key="fil_category")
f_status   = st.sidebar.multiselect("Status",   status_opts, key="fil_status")

DATE_COLS_FOR_FILTER = ["Assigned Date", "ETA", "Date of Completion"]
with st.sidebar.expander("Date range (matches ANY of the 3)"):
    use_date = st.checkbox("Enable date filter", value=False)
    d1 = st.date_input("From", value=date(2025, 1, 1))
    d2 = st.date_input("To",   value=date.today())
if use_date:
    d1s, d2s = pd.to_datetime(str(d1)), pd.to_datetime(str(d2))

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if f_person:   out = out[out["Person"].isin(f_person)]
    if f_category: out = out[out["Category"].isin(f_category)]
    if f_status:   out = out[out["Status"].isin(f_status)]
    if use_date:
        mask_any = False
        for c in DATE_COLS_FOR_FILTER:
            s = pd.to_datetime(out[c], errors="coerce")
            m = (s >= d1s) & (s <= d2s)
            mask_any = m if mask_any is False else (mask_any | m)
        out = out[mask_any] if isinstance(mask_any, pd.Series) else out
    return out

filtered = apply_filters(df_all)

# --------------------------- Tabs ---------------------------
tab_dash, tab_entry, tab_manage, tab_master = st.tabs(
    ["Dashboard", "Data Entry", "Upload / Edit / Delete", "Master Data"]
)

# ============================ Dashboard ============================
with tab_dash:
    st.subheader("Quick Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total (filtered)", len(filtered))
    with c2: st.metric("Not Live", (filtered["Status"] == "Not Live").sum())
    with c3: st.metric("Completed", (filtered["Status"] == "Completed").sum())
    with c4: st.metric("In Progress", (filtered["Status"] == "In Progress").sum())
    st.divider()
    st.subheader("Charts")
    if filtered.empty:
        st.info("No data in current filter.")
    else:
        colA, colB = st.columns([1, 1])
        with colA:
            status_counts = filtered["Status"].value_counts()
            fig1, ax1 = plt.subplots(figsize=(5, 4))
            ax1.pie(status_counts.values, labels=status_counts.index, autopct='%1.0f%%')
            ax1.set_title("Status distribution")
            st.pyplot(fig1)
        with colB:
            person_counts = filtered["Person"].value_counts()
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            ax2.bar(person_counts.index, person_counts.values)
            ax2.set_title("Tasks by Person")
            ax2.tick_params(axis='x', rotation=30)
            st.pyplot(fig2)

# ============================ Data Entry ============================
with tab_entry:
    st.subheader("Add / Update Task")
    keep_values = st.checkbox("Quick-add mode (keep values after save)", value=False)
    masters = st.session_state["masters"]
    all_categories = sorted(set(masters["Category"]) | set(df_all["Category"].dropna()))
    all_people     = sorted(set(masters["Person"])   | set(df_all["Person"].dropna()))
    all_statuses   = sorted(set(masters["Status"])   | set(df_all["Status"].dropna()))
    with st.form("task_form", clear_on_submit=not keep_values):
        col1, col2 = st.columns(2)
        with col1:
            category_choice = st.selectbox("Category", ["(Add New…)"] + list(all_categories), index=1 if all_categories else 0)
            category = st.text_input("New Category", value="") if category_choice == "(Add New…)" else category_choice
            task_name = st.text_input("Task Name")
            person_choice = st.selectbox("Person", ["(Add New…)"] + list(all_people), index=1 if all_people else 0)
            person = st.text_input("New Person", value="") if person_choice == "(Add New…)" else person_choice
            status_choice = st.selectbox("Status", ["(Add New…)"] + list(all_statuses), index=1 if all_statuses else 0)
            status = st.text_input("New Status", value="") if status_choice == "(Add New…)" else status_choice
        with col2:
            assigned_date = st.date_input("Assigned Date", value=None, key="assigned_date")
            eta = st.date_input("ETA", value=None, key="eta_date")
            completion_date = st.date_input("Date of Completion", value=None, key="completion_date")
            notes = st.text_area("Notes/Issues")
        if st.form_submit_button("Save Task"):
            changed = False
            if category and not _contains_ci(masters["Category"], category):
                masters["Category"].append(category); changed = True
            if person and not _contains_ci(masters["Person"], person):
                masters["Person"].append(person); changed = True
            if status and not _contains_ci(masters["Status"], status):
                masters["Status"].append(status); changed = True
            if changed:
                save_masters(masters)
                st.session_state["masters"] = load_masters()
            def norm_date(d): return str(d) if d else ""
            new_row = {
                "Category": category.strip(),
                "Task Name": task_name.strip(),
                "Person": person.strip(),
                "Status": status.strip(),
                "Assigned Date": norm_date(assigned_date),
                "ETA": norm_date(eta),
                "Date of Completion": norm_date(completion_date),
                "Notes/Issues": (notes or "").strip(),
            }
            st.session_state["tasks"] = pd.concat(
                [st.session_state["tasks"], pd.DataFrame([new_row])],
                ignore_index=True,
            )
            save_data(st.session_state["tasks"])
            st.success("Task added and saved.")
# ====================== Upload / Edit / Delete ======================
with tab_manage:
    st.subheader("Upload / Edit / Delete")
    # ---- Download / Upload / Disk utilities ----
    c1,c2,c3 = st.columns([1,1,2], vertical_alignment="top")
    with c1:
        if st.button("Reload from disk", use_container_width=True):
            st.session_state["tasks"]=load_data(); st.success("Reloaded from disk."); st.rerun()
        if st.button("Save to disk now", use_container_width=True):
            save_data(st.session_state["tasks"]); st.success("Saved to disk.")
    with c2:
        st.download_button("Download CSV Template (blank)", data=empty_df().to_csv(index=False).encode("utf-8"),
            file_name="tasks_template.csv", mime="text/csv", use_container_width=True)
        st.download_button("Download Current Data", data=st.session_state["tasks"].to_csv(index=False).encode("utf-8"),
            file_name="tasks_current.csv", mime="text/csv", use_container_width=True)
    with c3:
        st.write("Upload a CSV that matches the template columns.")
        uploaded=st.file_uploader("Choose CSV",type=["csv"],label_visibility="collapsed")
        mode=st.radio("Upload mode",["Append (add)","Replace (overwrite)"],horizontal=True)
        if uploaded is not None:
            try:
                new_df=read_csv_flexible(uploaded)
                missing=[c for c in COLUMNS if c not in new_df.columns]
                if missing: st.error("CSV is missing columns: "+", ".join(missing))
                else:
                    new_df=normalize(new_df)
                    if st.button("Apply Upload",use_container_width=True):
                        if mode.startswith("Replace"): st.session_state["tasks"]=new_df.copy()
                        else: st.session_state["tasks"]=pd.concat([st.session_state["tasks"],new_df],ignore_index=True)
                        save_data(st.session_state["tasks"]); st.success("Upload applied and saved."); st.rerun()
            except Exception as e: st.error(f"Could not read CSV: {e}")

    st.divider(); st.subheader("Edit or Delete Entries")
    compact=st.checkbox("Compact repeated values (visual only)",value=False)

    # ✅ Use filtered data so the grid respects sidebar filters
    base=filtered.copy(); base["__row_id"]=base.index
    show=base.copy()
    if compact and not show.empty:
        for col in ["Category","Person","Status"]:
            prev=None; vals=[]
            for v in show[col].tolist():
                if v==prev: vals.append("")
                else: vals.append(v); prev=v
            show[col]=vals

    cfg={c:st.column_config.TextColumn(c) for c in COLUMNS}
    cfg.update({
        "Delete":st.column_config.CheckboxColumn("Delete"),
        "__row_id":st.column_config.NumberColumn("__row_id",disabled=True)
    })

    # ✅ Select All for Delete
    select_all = st.checkbox("Select All for Delete")
    initial_delete = True if select_all else False

    edited=st.data_editor(
        show.assign(Delete=initial_delete),
        column_config=cfg,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_grid",
    )

    col_save,col_del,col_discard=st.columns(3)

    with col_save:
        if st.button("Save Edits",use_container_width=True):
            ed=edited.drop(columns=["Delete"],errors="ignore").copy().replace({"nan":"","None":""})
            for c in ["Assigned Date","ETA","Date of Completion"]:
                if c in ed.columns:
                    s=pd.to_datetime(ed[c],errors="coerce")
                    ed[c]=s.dt.strftime("%Y-%m-%d").fillna("")
            upd=ed[ed["__row_id"].notna()].copy()
            for _,r in upd.iterrows():
                idx=int(r["__row_id"])
                if idx in base.index:
                    base.loc[idx,COLUMNS]=r[COLUMNS].values
            new_rows=ed[ed["__row_id"].isna()][COLUMNS]
            if not new_rows.empty:
                base=pd.concat([base[COLUMNS],new_rows],ignore_index=True)
            base=normalize(base)
            st.session_state["tasks"]=base; save_data(base)
            st.success("Edits saved."); st.rerun()

    with col_del:
        if st.button("Delete Selected",use_container_width=True):
            ed=edited.copy(); del_mask=ed.get("Delete")
            if del_mask is None:
                st.info("No rows selected")
            else:
                del_mask=del_mask.fillna(False)
                ids=ed.loc[del_mask,"__row_id"].dropna().astype(int).tolist()
                base2=base.drop(index=ids,errors="ignore")
                new_rows_to_add=ed[~del_mask & ed["__row_id"].isna()][COLUMNS].replace({"nan":"","None":""})
                if not new_rows_to_add.empty:
                    base2=pd.concat([base2[COLUMNS],new_rows_to_add],ignore_index=True)
                base2=normalize(base2)
                st.session_state["tasks"]=base2; save_data(base2)
                st.success("Deleted rows."); st.rerun()

    with col_discard:
        if st.button("Discard Edits (Reload)",use_container_width=True):
            st.session_state["tasks"]=load_data(); st.info("Edits discarded."); st.rerun()

# ============================ Master Data ============================
with tab_master:
    st.subheader("Master Data (manage lists)")
    masters = st.session_state["masters"]
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Categories**")
        cat_new = st.text_input("Add Category", key="add_cat")
        if st.button("Save Category"):
            if cat_new.strip() and not _contains_ci(masters["Category"], cat_new):
                masters["Category"].append(cat_new.strip())
                save_masters(masters)
                st.session_state["masters"] = load_masters()
                st.success("Category added")
                st.rerun()
        st.dataframe(pd.DataFrame({"Category": masters["Category"]}), use_container_width=True)
    with col2:
        st.write("**People**")
        per_new = st.text_input("Add Person", key="add_person")
        if st.button("Save Person"):
            if per_new.strip() and not _contains_ci(masters["Person"], per_new):
                masters["Person"].append(per_new.strip())
                save_masters(masters)
                st.session_state["masters"] = load_masters()
                st.success("Person added")
                st.rerun()
        st.dataframe(pd.DataFrame({"Person": masters["Person"]}), use_container_width=True)
    with col3:
        st.write("**Statuses**")
        stat_new = st.text_input("Add Status", key="add_status")
        if st.button("Save Status"):
            if stat_new.strip() and not _contains_ci(masters["Status"], stat_new):
                masters["Status"].append(stat_new.strip())
                save_masters(masters)
                st.session_state["masters"] = load_masters()
                st.success("Status added")
                st.rerun()
        st.dataframe(pd.DataFrame({"Status": masters["Status"]}), use_container_width=True)
