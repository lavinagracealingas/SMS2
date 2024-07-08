import streamlit as st
import calendar
from datetime import datetime
import pandas as pd
import numpy as np
from streamlit_option_menu import option_menu
import pickle
from pathlib import Path
import streamlit_authenticator as stauth
from streamlit_pandas_profiling import st_profile_report
import sqlite3
import plotly.express as px
import re

conn = sqlite3.connect('../studentmonitor.db', check_same_thread=False)
cur = conn.cursor()

def app():
    def createProspectus():
        cur.execute(
            """CREATE TABLE IF NOT EXISTS prospectus (
            CourseCode TEXT NOT NULL UNIQUE,
            CourseDesc TEXT NOT NULL,
            Units INTEGER NOT NULL,
            Semester TEXT NOT NULL,
            YearLevel TEXT NOT NULL,
            Classification TEXT NOT NULL,
            PRIMARY KEY(CourseCode))"""
        )

    def addProspectus(CourseCode, CourseDesc, Units, Semester, YearLevel, Classification):
        cur.execute("SELECT CourseCode FROM prospectus WHERE CourseCode=?", (CourseCode,))
        if cur.fetchone():
            st.warning("This CourseCode already exists.")
            return False
        cur.execute("INSERT INTO prospectus (CourseCode, CourseDesc, Units, Semester, YearLevel, Classification) VALUES (?,?,?,?,?,?)",
                    (CourseCode, CourseDesc, Units, Semester, YearLevel, Classification))
        conn.commit()
        return True

    def updateProspectus(CourseCode, CourseDesc, Units, Semester, YearLevel, Classification):
        cur.execute("SELECT CourseCode FROM prospectus WHERE CourseCode=?", (CourseCode,))
        if cur.fetchone() is None:
            st.warning("This CourseCode does not exist.")
            return False
        cur.execute("UPDATE prospectus SET CourseDesc=?, Units=?, Semester=?, YearLevel=?, Classification=? WHERE CourseCode=?",
                    (CourseDesc, Units, Semester, YearLevel, Classification, CourseCode))
        conn.commit()
        return True

    def deleteProspectus(CourseCode):
        cur.execute("SELECT CourseCode FROM prospectus WHERE CourseCode=?", (CourseCode,))
        if cur.fetchone() is None:
            st.warning("This CourseCode does not exist.")
            return False
        cur.execute("DELETE FROM prospectus WHERE CourseCode=?", (CourseCode,))
        conn.commit()
        return True       

    def get_prospectus_details(CourseCode):
        cur.execute("SELECT * FROM prospectus WHERE CourseCode=?", (CourseCode,))
        return cur.fetchone()

    def fetch_prospectus_data(lvl, sem):
        query = f"""
        SELECT p.CourseCode, p.Units, p.Semester, p.YearLevel, p.Classification, r.Prerequisite, r.Corequisite
        FROM prospectus p
        LEFT JOIN requisite r ON p.CourseCode = r.CourseCode
        WHERE p.YearLevel LIKE '%{lvl}%' AND p.Semester LIKE '%{sem}%'
        """
        prospectus = pd.read_sql_query(query, conn)
        return prospectus

    def fetch_all_prospectus_data():
        query = """
        SELECT p.CourseCode, p.CourseDesc, p.Units, p.Semester, p.YearLevel, p.Classification, r.Prerequisite, r.Corequisite
        FROM prospectus p
        LEFT JOIN requisite r ON p.CourseCode = r.CourseCode"""
        all_prospectus = pd.read_sql_query(query, conn)
        return all_prospectus

    def get_summer_record_count(lvl):
        cur.execute(f"SELECT COUNT(*) FROM prospectus WHERE YearLevel LIKE '%{lvl}%' AND Semester LIKE '%Summer%'")
        return cur.fetchone()[0]

    def createRequisite():
        cur.execute(
            """CREATE TABLE IF NOT EXISTS requisite (
            CourseCode TEXT,
            Corequisite TEXT,
            Prerequisite TEXT,
            FOREIGN KEY(CourseCode) REFERENCES prospectus(CourseCode))"""
        )

    def updateRequisite(CourseCode, Prerequisite, Corequisite):
        cur.execute("SELECT CourseCode FROM requisite WHERE CourseCode=?", (CourseCode,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO requisite (CourseCode, Prerequisite, Corequisite) VALUES (?,?,?)",
                        (CourseCode, Prerequisite, Corequisite))
        else:
            cur.execute("UPDATE requisite SET Prerequisite=?, Corequisite=? WHERE CourseCode=?",
                        (Prerequisite, Corequisite, CourseCode))
        conn.commit()

    def get_prerequisite_details(CourseCode):
        cur.execute("SELECT Prerequisite FROM requisite WHERE CourseCode=?", (CourseCode,))
        req = cur.fetchone()
        if req:
            return req
        else:
            return []
    
    def get_corequisite_details(CourseCode):
        cur.execute("SELECT Corequisite FROM requisite WHERE CourseCode=?", (CourseCode,))
        req = cur.fetchone()
        if req:
            return req
        else:
            return []

    def fetch_all_prospectus():
        query = "SELECT CourseCode, CourseDesc FROM prospectus"
        prospectus = pd.read_sql_query(query, conn)
        return prospectus

    # Set up session state to store operation success
    if 'operation_success' not in st.session_state:
        st.session_state.operation_success = None
    if 'delete_confirm' not in st.session_state:
        st.session_state.delete_confirm = False
    if 'course_to_delete' not in st.session_state:
        st.session_state.course_to_delete = None

    # ------------ NAVIGATION ------------
    selected = option_menu(
        menu_title=None,
        options=["Course Registration", "Prospectus"],
        icons=["clipboard-fill", "folder-fill"],
        orientation="horizontal",
    )

    # ------------ SETTINGS ------------
    units = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5"]
    semester = ["1st Sem", "2nd Sem", "Summer"]
    yearlevel = ["1", "2", "3", "4"]
    classification = ["Major", "Minor", "Core"]
    page_icon = ":green_book:"
    layout = "centered"

    if selected == "Course Registration":
        if st.session_state.operation_success:
            st.success(st.session_state.operation_success)
            st.session_state.operation_success = None  # Reset the flag

        # ------------ INPUT AND SAVE PERIODS ------------
        st.header("Course Registration")

        cur.execute("SELECT CourseCode, CourseDesc FROM prospectus")
        prospectus = cur.fetchall()
        prospectus_dict = {coursecode: sid for sid, coursecode in prospectus}

        selected_coursedesc = st.selectbox("Select Course to Update", options=[""] + list(prospectus_dict.keys()))
        prospectus_details = None

        if selected_coursedesc:
            course_code = prospectus_dict[selected_coursedesc]
            prospectus_details = get_prospectus_details(course_code)

        with st.form("entry_form", clear_on_submit=True):
            coursecode = st.text_input("Course Code", value=prospectus_details[0] if prospectus_details else "", placeholder="STT155")
            coursedescription = st.text_input("Course Description", value=prospectus_details[1] if prospectus_details else "", placeholder="Categorical Data Analysis")

            col1, col2, col3, col4 = st.columns(4)
            selected_units = col1.selectbox("Units", units, index=units.index(str(prospectus_details[2])) if prospectus_details and str(prospectus_details[2]) in units else 0, key="units")
            selected_yearlevel = col2.selectbox("Year Level", yearlevel, index=yearlevel.index(prospectus_details[4]) if prospectus_details and prospectus_details[4] in yearlevel else 0, key="yrlvl")
            selected_semester = col3.selectbox("Semester", semester, index=semester.index(prospectus_details[3]) if prospectus_details and prospectus_details[3] in semester else 0, key="sem")
            selected_classification = col4.selectbox("Classification", classification, index=classification.index(prospectus_details[5]) if prospectus_details and prospectus_details[5] in classification else 0, key="class")

            col1, col2, col3 = st.columns(3)
            with col1:
                submitted = st.form_submit_button("Register")
                if submitted:
                    if all([coursecode, coursedescription, selected_units, selected_semester, selected_yearlevel, selected_classification]):
                        success = addProspectus(coursecode, coursedescription, selected_units, selected_semester, selected_yearlevel, selected_classification)
                        if success:
                            st.session_state.operation_success = "Data saved successfully."
                            st.experimental_rerun()
                    else:
                        st.warning("Please fill out all required fields.")       
            
            with col2:
                updated = st.form_submit_button("Update")
                if updated:
                    if all([coursecode, coursedescription, selected_units, selected_semester, selected_yearlevel, selected_classification]):
                        success = updateProspectus(coursecode, coursedescription, selected_units, selected_semester, selected_yearlevel, selected_classification)
                        if success:
                            st.session_state.operation_success = "Data updated successfully."
                            st.experimental_rerun()
                    else:
                        st.warning("Please fill out all required fields.")
                
            with col3:
                deleted = st.form_submit_button("Delete")
                if deleted:
                    if all([coursecode, coursedescription, selected_units, selected_semester, selected_yearlevel, selected_classification]):
                        @st.experimental_dialog("Confirm Deletion")
                        def confirm_deletion_dialog():
                            st.write(f"Are you sure you want to delete the course: {course_code}?")
                            if st.button("Yes"):
                                deleteProspectus(coursecode)
                                st.session_state.operation_success = f"Course Code {course_code} deleted successfully." 
                                st.experimental_rerun()
                            elif st.button("No"):
                                st.experimental_rerun()
                        
                        confirm_deletion_dialog()
                
                # Check if operation success message is set
                if st.session_state.get("operation_success"):
                    st.success(st.session_state.operation_success)
                    st.session_state.operation_success = None

    # ------------ PROSPECTUS ------------
    if selected == "Prospectus":
        st.header("Prospectus")
        prospectus_data = fetch_all_prospectus_data()

        selected_coursedesc = st.selectbox("Select Course Description", options=[""] + prospectus_data['CourseDesc'].tolist())
        course_code = None
        prereq_details = []
        coreq_details = []

        if selected_coursedesc:
            course_code = prospectus_data.loc[prospectus_data['CourseDesc'] == selected_coursedesc, 'CourseCode'].iloc[0]
            if course_code:
                pre_req = get_prerequisite_details(course_code)
                if pre_req:
                    prereq_details = re.split(",\s",pre_req[0])
                co_req = get_corequisite_details(course_code)
                if co_req:
                    coreq_details = re.split(",\s",co_req[0])

        available_courses = prospectus_data['CourseDesc'].tolist()

        with st.form("update_requisite_form"):
            col1, col2 = st.columns(2)

            with col1:
                # Display course descriptions, store corresponding course codes
                # default_prereq_desc = list(prereq_details) if len(prereq_details) >=1 else []
                default_prereq_desc = prospectus_data.loc[prospectus_data['CourseCode'].isin(prereq_details), 'CourseDesc'].tolist()

                selected_prereq_desc = st.multiselect("Prerequisite", options=available_courses, default=default_prereq_desc)

            with col2:
                # Display course descriptions, store corresponding course codes
                default_coreq_desc = prospectus_data.loc[prospectus_data['CourseCode'].isin(coreq_details), 'CourseDesc'].tolist()
                selected_coreq_desc = st.multiselect("Corequisite", options=available_courses, default=default_coreq_desc)
                
            
            if st.form_submit_button("Update Requisite"):
                selected_prereq = [prospectus_data.loc[prospectus_data['CourseDesc'].isin(selected_prereq_desc), 'CourseCode'].iloc[0] for desc in selected_prereq_desc]
                selected_coreq = [prospectus_data.loc[prospectus_data['CourseDesc'].isin(selected_coreq_desc), 'CourseCode'].iloc[0] for desc in selected_coreq_desc]
                updateRequisite(course_code, ', '.join(selected_prereq), ', '.join(selected_coreq))
                st.success("Requisite updated successfully.")


        # Search term input
        search_query = st.text_input("Search", "")

        all_data = []
        for lvl in yearlevel:
            for sem in semester:
                if sem == "Summer" and get_summer_record_count(lvl) == 0:
                    continue

                # Construct SQL query with filters
                query = f"""
                SELECT p.CourseCode, p.CourseDesc, p.Units, p.Semester, p.YearLevel, p.Classification, 
                    r.Prerequisite AS PrereqCode, r.Corequisite AS CoreqCode
                FROM prospectus p
                LEFT JOIN requisite r ON p.CourseCode = r.CourseCode
                WHERE p.YearLevel LIKE '%{lvl}%' AND p.Semester LIKE '%{sem}%'"""

                # Add search condition if search_query is not empty
                if search_query:
                    # Split search_query into individual terms
                    search_terms = search_query.split()
                    conditions = []

                    for term in search_terms:
                        conditions.append(f"(p.CourseCode LIKE '%{term}%' OR p.CourseDesc LIKE '%{term}%' OR p.Units = '{term}' OR p.Classification LIKE '%{term}%')")

                    query += " AND " + " AND ".join(conditions)

                # Fetch data based on constructed query
                prospectus_data = pd.read_sql_query(query, conn)

                if not prospectus_data.empty:
                    requisite_data = fetch_all_prospectus_data()
                    requisite_dict = requisite_data.set_index('CourseDesc')['CourseCode'].to_dict()

                    def map_requisites(requisites):
                        if requisites:
                            return ', '.join([requisite_dict.get(req.strip(), req.strip()) for req in requisites.split(', ')])
                        return ''

                    prospectus_data['PrereqCode'] = prospectus_data['PrereqCode'].apply(map_requisites)
                    prospectus_data['CoreqCode'] = prospectus_data['CoreqCode'].apply(map_requisites)

                    st.write(f"Year Level {lvl} - {sem}")
                    st.dataframe(prospectus_data[['CourseCode', 'CourseDesc', 'Units', 'Classification', 'PrereqCode', 'CoreqCode']])
                    total_units = prospectus_data['Units'].sum()
                    st.write(f"Total Units: {total_units}")
                    total_row = pd.DataFrame({"CourseCode": ["Total Units"], "CourseDesc": [""], "Units": [total_units], "Semester": [""], "YearLevel": [""], "Classification": [""], "PrereqCode": [""], "CoreqCode": [""]})
                    prospectus_data = pd.concat([prospectus_data, total_row], ignore_index=True)
                    all_data.append(prospectus_data)

        if all_data:
            combined_prospectus_data = pd.concat(all_data)

            # CSV Download button
            csv_data = combined_prospectus_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download the Prospectus as CSV",
                data=csv_data,
                file_name="Prospectus.csv",
                mime="text/csv",
            )