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
import Home, Student_Registration, Prospectus, Course_Assignment, Grade_Report, Dashboard
import plotly.graph_objects as go

conn = sqlite3.connect('studentmonitor.db', check_same_thread=False)
cur = conn.cursor()

names = ["Johniel Babiera", "Daisy Polestico"]
usernames = ["jbabiera","dpolestico"]

file_path = Path(__file__).parent/"hashed_pw.pkl"
with file_path.open("rb") as file:
    hashed_passwords = pickle.load(file)

authenticator = stauth.Authenticate(names,usernames,hashed_passwords, "application_system", "abcdef", cookie_expiry_days=0)

name, authentication_status, username = authenticator.login("Login","main")

if authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
elif authentication_status:
    st.title="Student Monitoring System"
    st.sidebar.success("Succesfully Logged in!")
    with st.sidebar:
        app = option_menu(
            menu_title="Main Menu",
            options=["Home", "Dashboard", "Student Registration", "Prospectus", "Course Assignment", "Grade Report"],
            icons=["house-fill", "stack", "person-lines-fill", "book-fill", "list-columns-reverse", "bar-chart-line-fill"],
            menu_icon = "cast",
            default_index=0,
        )

        def logout():
            st.session_state.logged_in = False
            st.session_state.authentication_status = None
            st.info("Logged out successfully!")
            st.rerun()

        if st.button("Log out"):
                logout()

    st.markdown("# Student Monitoring System")
    st.write(f'Welcome *{name}*')
    if app == "Home":
        Home.app()
    if app == "Dashboard":
        Dashboard.app()
    if app == "Student Registration":
        Student_Registration.app()
    if app == "Prospectus":
        Prospectus.app()
    if app == "Course Assignment":
        Course_Assignment.app()
    if app == "Grade Report":
        Grade_Report.app()

        conn.close()

