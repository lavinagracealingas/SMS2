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
    semesters = ["1st Term", "2nd Term", "Summer Term"]
    year_levels = ["1st", "2nd", "3rd", "4th"]
    grade_options = ["  ", "1.00", "1.25", "1.50", "1.75", "2.00", "2.25", "2.50", "2.75", "3.00", "5.00", "INC", "INPROG", "P", "F", "DRP", "W"]
    gradestatus_options = ["Passed", "Failed", "To be Determined","Dropped"]

    def get_course_data_with_status_counts(conn, year_level, semester):
        query = f"""
        SELECT p.CourseCode, p.CourseDesc, p.Units, ca.Semester, ca.YearLevel, 
        SUM(CASE WHEN ca.GradeStatus = 'Passed' THEN 1 ELSE 0 END) as PassedCount,
        SUM(CASE WHEN ca.GradeStatus = 'Failed' THEN 1 ELSE 0 END) as FailedCount,
        SUM(CASE WHEN ca.GradeStatus = 'Dropout' THEN 1 ELSE 0 END) as DroppedCount,
        SUM(CASE WHEN ca.GradeStatus = 'Withdrawn' THEN 1 ELSE 0 END) as WithdrawnCount,
        SUM(CASE WHEN ca.GradeStatus != 'Passed' THEN 1 ELSE 0 END) as RetakeCount
        FROM prospectus p
        LEFT JOIN courseassignment ca ON p.CourseCode = ca.CourseCode
        WHERE ca.YearLevel LIKE ? AND ca.Semester LIKE ?
        GROUP BY p.CourseCode, p.CourseDesc, p.Units, ca.Semester, ca.YearLevel
        """
        df = pd.read_sql_query(query, conn, params=(f'%{year_level}%', f'%{semester}%'))
        return df

    # Function to add or update grade
    def addOrUpdateGrade(StudentID, CourseCode, Grade, FinalGrade, GradeStatus):
        cur.execute(
            """UPDATE courseassignment 
            SET Grade = ?, FinalGrade = ?, GradeStatus = ?
            WHERE StudentID = ? AND CourseCode = ?""",
            (Grade, FinalGrade, GradeStatus, StudentID, CourseCode)
        )
        conn.commit()
        st.session_state.operation_success = "Grade has been added. If there is INC please update when accomplished."

    # Function to determine grade status
    def determineGradeStatus(grade):
        if grade in ["1.00", "1.25", "1.50", "1.75", "2.00", "2.25", "2.50", "2.75", "3.00", "P"]:
            return "Passed"
        elif grade in ["INC", "INPROG"]:
            return "To be Determined"
        elif grade == "W":
            return "Withdrawn"
        elif grade == "DRP":
            return "Dropout"
        else:
            return "Failed"

    if 'operation_success' not in st.session_state:
        st.session_state.operation_success = None

    # Fetching student IDs and names
    cur.execute("SELECT StudentID, Name FROM student")
    students = cur.fetchall()
    student_ids = [student[0] for student in students]
    student_names = {student[0]: student[1] for student in students}  # Dictionary for mapping StudentID to StudentName

    sub_selected = option_menu(
        menu_title=None,
        options=["Grade Evaluation", "Grade Status Enumeration"],
        icons=["clipboard-fill", "folder-fill"],
        orientation="horizontal",
        default_index=0
    )
    if sub_selected == "Grade Evaluation":
        st.header("Grade Evaluation")

        selected_student_name = st.selectbox("Select Student:", list(student_names.values()))
        selected_student_id = next(key for key, value in student_names.items() if value == selected_student_name)
        if selected_student_id:
            student_name = student_names[selected_student_id]
            st.write(f"Grades for {student_name} ({selected_student_id})")

            # Fetch the course assignments for the selected student with course descriptions
            grades_df = pd.read_sql_query(
                """SELECT ca.StudentID, ca.CourseCode, p.CourseDesc, ca.Grade, ca.FinalGrade, ca.GradeStatus, p.Units, ca.Semester, ca.YearLevel
                FROM courseassignment ca
                JOIN prospectus p ON ca.CourseCode = p.CourseCode
                WHERE ca.StudentID = ?
                ORDER BY ca.YearLevel, ca.Semester""",
                conn, params=(selected_student_id,)
            )

            if not grades_df.empty:
                def get_grade(row):
                    initial_grade = row['Grade']
                    final_grade = row['FinalGrade']
                    
                    non_numeric_grades = ["W", "P", "F", "INPROG"]

                    if pd.isna(initial_grade) or initial_grade.strip() == "" or initial_grade.strip() in non_numeric_grades:
                        return None  # Exclude these grades from calculation
                    
                    if initial_grade.strip() == "INC":
                        if pd.isna(final_grade) or final_grade.strip() == "":
                            return 5.00  # Default value for INC with no final grade
                        else:
                            try:
                                return float(final_grade)  # Convert final grade to float
                            except ValueError:
                                return 0.00  # Return 0.00 if final grade cannot be converted
                    elif initial_grade.strip() == "DRP":
                        return 5.00  # DRP equivalent to 5.00
                    else:
                        if pd.isna(final_grade) or final_grade.strip() == "":
                            try:
                                return float(initial_grade)  # Use initial grade as final grade if no final grade provided
                            except ValueError:
                                return 0.00  # Return 0.00 if initial grade cannot be converted
                        else:
                            try:
                                return float(final_grade)  # Convert final grade to float
                            except ValueError:
                                try:
                                    return float(initial_grade)  # Use initial grade if final grade cannot be converted
                                except ValueError:
                                    return 0.00  # Return 0.00 if neither can be converted

                def calculate_gpa(df):
                    valid_grades = df[~df['CourseCode'].isin(['NST001', 'NST002'])]

                    df.loc[~df['CourseCode'].isin(['NST001', 'NST002']), 'GradePoint'] = valid_grades.apply(get_grade, axis=1)
                    df.dropna(subset=['GradePoint'], inplace=True)

                    total_units = valid_grades['Units'].sum()
                    weighted_sum = (valid_grades['Units'] * df['GradePoint']).sum()

                    return round(weighted_sum / total_units, 5) if total_units > 0 else 0

                all_gpas = []
                all_cgpas = []
                running_total_units = 0
                running_weighted_sum = 0

                for year in year_levels:
                    for sem in semesters:
                        filtered_grades_df = grades_df[(grades_df['YearLevel'] == year) & (grades_df['Semester'] == sem)]
                        if not filtered_grades_df.empty:
                            st.write(f"{year} YearLevel - {sem}")

                            # Keep the Units column for GPA calculation
                            edited_df = filtered_grades_df.drop(columns=['Semester', 'YearLevel'])

                            edited_df = st.data_editor(
                                edited_df,
                                column_config={
                                    "CourseCode": st.column_config.TextColumn(width="medium", disabled=True),
                                    "CourseDesc": st.column_config.TextColumn(width="medium", disabled=True),
                                    "Grade": st.column_config.SelectboxColumn(
                                        "Initial Grade",
                                        options=grade_options,
                                        required=True
                                    ),
                                    "FinalGrade": st.column_config.SelectboxColumn(
                                        "Final Grade",
                                        options=grade_options,
                                        required=False
                                    ),
                                    "GradeStatus": st.column_config.TextColumn(width="medium", disabled=True)
                                }
                            )

                            if st.button(f"Submit Grades for {year} {sem}"):
                                for index, row in edited_df.iterrows():
                                    initial_grade = row['Grade']
                                    final_grade = row['FinalGrade']
                                    if initial_grade in ["INC", "INPROG"]:
                                        if final_grade is None or final_grade.strip() == "":
                                            grade_status = ""
                                        else:
                                            grade_status = determineGradeStatus(final_grade)
                                    else:
                                        final_grade = initial_grade
                                        grade_status = determineGradeStatus(final_grade)

                                    addOrUpdateGrade(selected_student_id, row['CourseCode'], initial_grade, final_grade, grade_status)
                                st.experimental_rerun()

                            gpa = calculate_gpa(filtered_grades_df)
                            all_gpas.append((year, sem, gpa))

                            valid_grades = filtered_grades_df[~filtered_grades_df['CourseCode'].isin(['NST001', 'NST002'])]
                            valid_grades['GradePoint'] = valid_grades.apply(get_grade, axis=1)
                            valid_grades = valid_grades.dropna(subset=['GradePoint'])

                            running_total_units += valid_grades['Units'].sum()
                            running_weighted_sum += (valid_grades['Units'] * valid_grades['GradePoint']).sum()
                            cgpa = round(running_weighted_sum / running_total_units, 5) if running_total_units > 0 else 0
                            all_cgpas.append((year, sem, cgpa))

                            st.write(f"GPA: {gpa} | CGPA: {cgpa}")

                overall_cgpa = calculate_gpa(grades_df)
                st.write(f"Overall CGPA: {overall_cgpa}")

                # Data Visualization with Plotly Express for GPA
                if all_gpas:
                    gpa_df = pd.DataFrame(all_gpas, columns=['YearLevel', 'Semester', 'GPA'])
                    gpa_df['Semester'] = pd.Categorical(gpa_df['Semester'], categories=semesters, ordered=True)
                    gpa_df.sort_values(by=['YearLevel', 'Semester'], inplace=True)

                    fig_gpa = px.line(gpa_df, x='Semester', y='GPA', color='YearLevel', markers=True, title='GPA Progression per Semester')
                    st.plotly_chart(fig_gpa)

                # Data Visualization with Plotly Express for CGPA
                if all_cgpas:
                    cgpa_df = pd.DataFrame(all_cgpas, columns=['YearLevel', 'Semester', 'CGPA'])
                    cgpa_df['Semester'] = pd.Categorical(cgpa_df['Semester'], categories=semesters, ordered=True)
                    cgpa_df.sort_values(by=['YearLevel', 'Semester'], inplace=True)

                    fig_cgpa = px.line(cgpa_df, x='Semester', y='CGPA', color='YearLevel', markers=True, title='CGPA Progression per Semester')
                    st.plotly_chart(fig_cgpa)
            else:
                st.warning("No course assignments found for the selected student.")

    elif sub_selected == "Grade Status Enumeration":
        st.header("Grade Status Enumeration")
        year_levels = ["1st", "2nd", "3rd", "4th"]
        semesters = ["1st Term", "2nd Term", "Summer Term"]
        
        selected_year_level = st.selectbox("Select Year Level:", year_levels)
        selected_semester = st.selectbox("Select Semester:", semesters)
        
        if selected_year_level and selected_semester:
            course_data_df = get_course_data_with_status_counts(conn, selected_year_level, selected_semester)
            
            if not course_data_df.empty:
                st.subheader(f'Course Data for {selected_year_level} Year Level, {selected_semester} Semester')
                # Drop the columns StudentID, YearLevel, and Semester before displaying
                course_display_df = course_data_df.drop(columns=['Units','YearLevel', 'Semester'])
                st.dataframe(course_display_df)
                
                # Visualization using Plotly
                fig = px.bar(course_data_df, x='CourseCode', y=['PassedCount', 'FailedCount', 'DroppedCount', 'WithdrawnCount', 'RetakeCount'],
                            title=f'Course Status Counts for {selected_year_level} Year Level, {selected_semester}')
                st.plotly_chart(fig)
            else:
                st.warning("No data found for the selected year level and semester.")