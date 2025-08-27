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
    cfg.update({"Delete":st.column_config.CheckboxColumn("Delete"),
                "__row_id":st.column_config.NumberColumn("__row_id",disabled=True)})

    # ✅ Select All for Delete checkbox
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
                if c in ed.columns: s=pd.to_datetime(ed[c],errors="coerce"); ed[c]=s.dt.strftime("%Y-%m-%d").fillna("")
            upd=ed[ed["__row_id"].notna()].copy()
            for _,r in upd.iterrows():
                idx=int(r["__row_id"]); 
                if idx in base.index: base.loc[idx,COLUMNS]=r[COLUMNS].values
            new_rows=ed[ed["__row_id"].isna()][COLUMNS]
            if not new_rows.empty: base=pd.concat([base[COLUMNS],new_rows],ignore_index=True)
            base=normalize(base); st.session_state["tasks"]=base; save_data(base)
            st.success("Edits saved."); st.rerun()
    with col_del:
        if st.button("Delete Selected",use_container_width=True):
            ed=edited.copy(); del_mask=ed.get("Delete")
            if del_mask is None: st.info("No rows selected")
            else:
                del_mask=del_mask.fillna(False)
                ids=ed.loc[del_mask,"__row_id"].dropna().astype(int).tolist()
                base2=base.drop(index=ids,errors="ignore")
                new_rows_to_add=ed[~del_mask & ed["__row_id"].isna()][COLUMNS].replace({"nan":"","None":""})
                if not new_rows_to_add.empty: base2=pd.concat([base2[COLUMNS],new_rows_to_add],ignore_index=True)
                base2=normalize(base2); st.session_state["tasks"]=base2; save_data(base2)
                st.success("Deleted rows."); st.rerun()
    with col_discard:
        if st.button("Discard Edits (Reload)",use_container_width=True):
            st.session_state["tasks"]=load_data(); st.info("Edits discarded."); st.rerun()
