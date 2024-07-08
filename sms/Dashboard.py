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
import plotly.graph_objects as go

conn = sqlite3.connect('../studentmonitor.db', check_same_thread=False)
cur = conn.cursor()

def app():
    st.subheader("Dashboard",  divider='red')
    def fetch_semesters_and_year_levels():
        cur.execute("SELECT DISTINCT Semester FROM courseassignment")
        semesters = [row[0] for row in cur.fetchall()]

        cur.execute("SELECT DISTINCT YearLevel FROM courseassignment")
        year_levels = [row[0] for row in cur.fetchall()]

        return semesters, year_levels

    def count_inc_students():
        cur.execute("""
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE Grade = 'INC'
            AND Semester = ? 
            AND YearLevel = ?
        """, (selected_semester, selected_year_level))
        result = cur.fetchone()
        return result[0] if result else 0

    def count_withdrawn_students():
        cur.execute("""
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE GradeStatus = 'Withdrawn'
            AND Semester = ? 
            AND YearLevel = ?
        """, (selected_semester, selected_year_level))
        result = cur.fetchone()
        return result[0] if result else 0

    def count_failing_students():
        cur.execute("""
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE FinalGrade = '5.00'
            AND Semester = ? 
            AND YearLevel = ?
        """, (selected_semester, selected_year_level))
        result = cur.fetchone()
        return result[0] if result else 0

    def get_student_grades():
        query = """
            SELECT ca.StudentID, ca.CourseCode, p.Units, ca.Grade, ca.FinalGrade
            FROM courseassignment ca
            JOIN prospectus p ON ca.CourseCode = p.CourseCode
            WHERE ca.Semester = ? 
            AND ca.YearLevel = ?
        """
        grades_df = pd.read_sql_query(query, conn, params=(selected_semester, selected_year_level))
        return grades_df

    def get_initial_grade_value(initial_grade, final_grade):
        if initial_grade in ["1.00", "1.25", "1.50", "1.75", "2.00", "2.25", "2.50", "2.75", "3.00"]:
            return float(initial_grade)
        elif initial_grade in ["INC", "INPROG"] and final_grade in ["1.00", "1.25", "1.50", "1.75", "2.00", "2.25", "2.50", "2.75", "3.00"]:
            return float(final_grade)
        elif initial_grade == "5.00":
            return 5.00
        else:
            return None

    def calculate_gpa(grades_df):
        gpa_data = []
        for student_id, group in grades_df.groupby('StudentID'):
            valid_grades = group[~group['CourseCode'].isin(['NST001', 'NST002'])]
            valid_grades['GradePoint'] = valid_grades.apply(lambda row: get_initial_grade_value(row['Grade'], row['FinalGrade']), axis=1)
            valid_grades.dropna(subset=['GradePoint'], inplace=True)
            total_units = valid_grades['Units'].sum()
            weighted_sum = (valid_grades['Units'] * valid_grades['GradePoint']).sum()
            if total_units > 0:
                gpa = weighted_sum / total_units
                gpa_data.append((student_id, gpa))
        return pd.DataFrame(gpa_data, columns=['StudentID', 'GPA'])
    
    def calculate_cgpa(grades_df):
        cgpa_data = []
        for student_id, group in grades_df.groupby('StudentID'):
            running_total_units = 0
            running_weighted_sum = 0
            valid_grades = group[~group['CourseCode'].isin(['NST001', 'NST002'])]
            valid_grades['GradePoint'] = valid_grades.apply(lambda row: get_initial_grade_value(row['Grade'], row['FinalGrade']), axis=1)
            valid_grades.dropna(subset=['GradePoint'], inplace=True)
            running_total_units += valid_grades['Units'].sum()
            running_weighted_sum += (valid_grades['Units'] * valid_grades['GradePoint']).sum()
            if running_total_units > 0:
                cgpa = round(running_weighted_sum / running_total_units, 5)
                cgpa_data.append((student_id, cgpa))
        return pd.DataFrame(cgpa_data, columns=['StudentID', 'CGPA'])

    def calculate_average_gpa_cgpa():
        final_grades_df = get_student_grades()
        gpa_df = calculate_gpa(final_grades_df)
        cgpa_df = calculate_cgpa(final_grades_df)
        avg_gpa = gpa_df['GPA'].mean()
        avg_cgpa = cgpa_df['CGPA'].mean()
        return avg_gpa, avg_cgpa


    def count_students_with_gpa_above(gpa_threshold):
        initial_grades_df = get_student_grades()
        gpa_df = calculate_gpa(initial_grades_df)
        return gpa_df[gpa_df['GPA'] > gpa_threshold].shape[0]

    def count_students_with_gpa_below(gpa_threshold):
        initial_grades_df = get_student_grades()
        gpa_df = calculate_gpa(initial_grades_df)
        return gpa_df[gpa_df['GPA'] < gpa_threshold].shape[0]

    def count_awardees_students(min_gpa, max_gpa):
        initial_grades_df = get_student_grades()
        gpa_df = calculate_gpa(initial_grades_df)
        return gpa_df[(gpa_df['GPA'] >= min_gpa) & (gpa_df['GPA'] <= max_gpa)].shape[0]
    

    def count_students_with_condition(query, params=None):
        if params is None:
            cur.execute(query)
        else:
            cur.execute(query, params)
        result = cur.fetchone()
        return result[0] if result else 0

    def calculate_rates(selected_semester, selected_year_level):
        total_students_query = "SELECT COUNT(*) FROM student"
        total_students = count_students_with_condition(total_students_query)

        
        survival_rate_query = """
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE YearLevel = ?
        """
        survival_rate = count_students_with_condition(survival_rate_query, (selected_year_level,))

        failure_rate = 100 - survival_rate

        completion_rate_query = """
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE YearLevel = ? AND FinalGrade NOT IN ('INC', 'INPROG')
        """
        completion_rate = count_students_with_condition(completion_rate_query, (selected_year_level,))

        promotion_rate_query = """
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE YearLevel = ? + 1
        """
        promotion_rate = count_students_with_condition(promotion_rate_query, (selected_year_level,))

        dropout_rate_query = """
            SELECT COUNT(DISTINCT StudentID) 
            FROM courseassignment 
            WHERE GradeStatus = 'Dropout'
        """
        dropout_rate = count_students_with_condition(dropout_rate_query)

        return survival_rate, failure_rate, completion_rate, promotion_rate, dropout_rate

    semesters, year_levels = fetch_semesters_and_year_levels()

    col1, col2 = st.columns(2)
    selected_year_level = col1.selectbox('Select Year Level', year_levels)
    selected_semester = col2.selectbox('Select Semester', semesters)

    # Calculate rates
    survival_rate, failure_rate, completion_rate, promotion_rate, dropout_rate = calculate_rates(selected_semester, selected_year_level)

    cur.execute("SELECT StudentID, Name FROM student")
    students = cur.fetchall()
    student_total = len(students)
    avg_gpa, avg_cgpa =calculate_average_gpa_cgpa()
    students_inc = count_inc_students()
    students_withdraw = count_withdrawn_students()
    failing_students = count_failing_students()
    rl_students = count_awardees_students(1.00, 1.20)
    cl_students = count_awardees_students(1.21, 1.44)
    dl_students = count_awardees_students(1.45, 1.75)
    students_below_gpa = count_students_with_gpa_below(2.50)
    students_above_gpa = count_students_with_gpa_above(2.50)

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("Number of students", student_total, delta=0 , delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("Survival Rate", survival_rate, "%", delta_color="normal")
    with col3:
        with st.container(border=True):
            st.metric("Completion Rate", completion_rate, "%", delta_color="normal")

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("Promotion Rate", promotion_rate, "%", delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("Failure Rate", failure_rate, "%", delta_color="normal")
    with col3:
        with st.container(border=True):
            st.metric("Dropout Rate", dropout_rate, "%", delta_color="normal")
    
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.metric("Average GPA of Students", avg_gpa, delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("Average CGPA of Students", avg_cgpa, delta_color="normal")
    
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("No. of Students with INC", students_inc, delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("No. of Students Withdrawn", students_withdraw, delta_color="normal")
    with col3:
        with st.container(border=True):
            st.metric("No. of Students with Failing Grades", failing_students, delta=0 , delta_color="normal")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("Number of RL Awardees", rl_students, delta=0 , delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("Number of CL Awardees", cl_students, delta=0 , delta_color="normal")
    with col3:
        with st.container(border=True):
            st.metric("Number of DL Awardees", dl_students, delta=0 , delta_color="normal")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.metric("No. of Students with GPA below 2.50", students_below_gpa, delta=0 , delta_color="normal")
    with col2:
        with st.container(border=True):
            st.metric("No. of Students with GPA above 2.50", students_above_gpa, delta=0 , delta_color="normal")
    

