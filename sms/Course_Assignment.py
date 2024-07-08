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
    def addCourseAssignment(StudentID, CourseCode, Grade, FinalGrade, GradeStatus, AcademicYear, YearLevel, Semester):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS courseassignment (
                EnrollID INTEGER PRIMARY KEY AUTOINCREMENT,
                StudentID TEXT NOT NULL,
                CourseCode TEXT NOT NULL,
                Grade TEXT,
                FinalGrade TEXT,
                GradeStatus TEXT,
                AcademicYear TEXT,
                YearLevel TEXT,
                Semester TEXT,
                FOREIGN KEY(StudentID) REFERENCES student(StudentID),
                FOREIGN KEY(CourseCode) REFERENCES prospectus(CourseCode)
            )"""
        )
        cur.execute(
            "SELECT * FROM courseassignment WHERE StudentID = ? AND CourseCode = ? AND AcademicYear = ? AND YearLevel = ? AND Semester = ?",
            (StudentID, CourseCode, AcademicYear, YearLevel, Semester)
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO courseassignment (StudentID, CourseCode, Grade, FinalGrade, GradeStatus, AcademicYear, YearLevel, Semester) VALUES (?,?,?,?,?,?,?,?)",
                (StudentID, CourseCode, Grade, FinalGrade, GradeStatus, AcademicYear, YearLevel, Semester)
            )
            conn.commit()
            return True
        return False

    # Function to delete course assignment
    def deleteCourseAssignment(StudentID, CourseCode):
        cur.execute("DELETE FROM courseassignment WHERE StudentID = ? AND CourseCode = ?", (StudentID, CourseCode))
        conn.commit()

    # Function to update course assignment
    def updateCourseAssignment(StudentID, CourseCode, YearLevel, Semester):
        cur.execute(
            """UPDATE courseassignment 
            SET YearLevel = ?,Semester = ?
            WHERE StudentID = ? AND CourseCode = ?""",
            (YearLevel, Semester, StudentID, CourseCode)
        )
        conn.commit()

    if 'operation_success' not in st.session_state:
        st.session_state.operation_success = None
    if 'delete_confirmation' not in st.session_state:
        st.session_state.delete_confirmation = False

    # Settings
    semesters = ["1st Term", "2nd Term", "Summer Term"]
    year_levels = ["1st", "2nd", "3rd", "4th"]
    #year_levels.sort(reverse=True)  # Sort years in decreasing order
    #status_options = ["taken", "not taken"]

    # Fetching student IDs and names
    cur.execute("SELECT StudentID, Name FROM student")
    students = cur.fetchall()
    student_ids = [student[0] for student in students]
    student_names = {student[0]: student[1] for student in students}  # Dictionary for mapping StudentID to StudentName

    # Generate list of school years
    current_year = datetime.today().year
    school_year = [f"{current_year-1}-{current_year}", f"{current_year}-{current_year+1}", f"{current_year+1}-{current_year+2}"]

    # Fetching course codes (assuming course codes are present in the 'prospectus' table)
    cur.execute("SELECT CourseCode, CourseDesc FROM prospectus")
    courses = cur.fetchall()
    course_codes = [course[0] for course in courses]
    course_descriptions = {course[0]: course[1] for course in courses}  # Dictionary for mapping CourseCode to CourseDescription

    # Main Navigation
    selected = option_menu(
        menu_title=None,
        options=["Course Assignment", "Course Directory"],  
        icons=["clipboard-fill", "folder-fill", "file-person-fill"],
        orientation="horizontal",
    )

    # Course Assignment Page
    if selected == "Course Assignment":
        sub_selected = option_menu(
            menu_title=None,
            options=["Assign Course", "Manage Assignments"],
            orientation="vertical",
            default_index=0
        )

        if sub_selected == "Assign Course":
            st.header("Assign Course")

            with st.form("Assign Course", clear_on_submit=True):
                acad_year = st.selectbox("Select Academic Year:", school_year)

                col1, col2 = st.columns(2)
                selected_year = col1.selectbox("Select Year Level:", year_levels, key="year")
                selected_semester = col2.selectbox("Select Semester:", semesters, key="sem")

                "---"
                selected_student_name = st.selectbox("Select Student:", list(student_names.values()))
                selected_student_id = next(key for key, value in student_names.items() if value == selected_student_name)
                
                selected_course_descriptions = st.multiselect("Enrolled Courses", list(course_descriptions.values()))
                selected_course_codes = [key for key, value in course_descriptions.items() if value in selected_course_descriptions]
                

                "---"
                submit = st.form_submit_button("Assign")

                if submit:
                    success_count = 0                    
                    error_messages = []
                
                    for selected_course_code in selected_course_codes:
                        
                        # Check for prerequisites and corequisites
                        cur.execute("SELECT Prerequisite, Corequisite FROM requisite WHERE CourseCode = ?", (selected_course_code,))
                        requisite = cur.fetchone()
                        prereq_met = True
                        coreq_met = True

                        if requisite:
                            prereq, coreq = requisite

                            # Check prerequisites
                            if prereq:
                                prereq_courses = prereq.split(', ')
                                for prereq_course in prereq_courses:
                                    cur.execute(
                                        "SELECT * FROM courseassignment WHERE StudentID = ? AND CourseCode = ? ",
                                        (selected_student_id, prereq_course)
                                    )
                                    if cur.fetchone() is None:
                                        prereq_met = False
                                        error_messages.append(f"Prerequisite {prereq_course} not taken.")

                            # Check corequisites
                            if coreq:
                                coreq_courses = coreq.split(', ')
                                if not any(course in selected_course_codes  for course in coreq_courses):
                                    coreq_met = False
                                    error_messages.append(f"Corequisite {', '.join(coreq_courses)} not selected.")

                        if prereq_met and coreq_met:
                            success = addCourseAssignment(selected_student_id, selected_course_code, None, None, None, acad_year, selected_year, selected_semester)
                            if success:
                                success_count += 1
                        else:
                            error_messages.append(f"Cannot assign {selected_course_code} due to prerequisite/corequisite issues.")

                    if success_count > 0:
                        st.success(f'{success_count} course assignment(s) have been successful')
                    if error_messages:
                        for error in error_messages:
                            st.error(error)

        elif sub_selected == "Manage Assignments":
            st.header("Manage Course Assignments")
            assignments = pd.read_sql_query(
                "SELECT ca.StudentID, ca.CourseCode, ca.Semester, ca.YearLevel, ca.AcademicYear "
                "FROM courseassignment ca "
                "ORDER BY ca.YearLevel DESC, ca.Semester", conn)

            # Fetch course descriptions
            courses = pd.read_sql_query(
                "SELECT p.CourseCode, p.CourseDesc "
                "FROM prospectus p", conn)
            
            # Create a mapping from CourseCode to CourseDescription
            course_mapping = dict(zip(courses['CourseCode'], courses['CourseDesc']))
            inverse_course_mapping = {v: k for k, v in course_mapping.items()}

            selected_student_name = st.selectbox("Select Student:", list(student_names.values()))
            selected_student_id = next(key for key, value in student_names.items() if value == selected_student_name)
            
            # Fetch the assignments for the selected student
            student_assignments = assignments[assignments['StudentID'] == selected_student_id]
            
            if student_assignments.empty:
                st.warning("No 'taken' course assignments found for the selected student.")
            else:
                # Map course codes to course descriptions for the select box
                student_assignments['CourseDesc'] = student_assignments['CourseCode'].map(course_mapping)
                
                selected_course_update = st.selectbox("Select Course Assigned:", student_assignments['CourseDesc'].unique())
                selected_course_code = inverse_course_mapping[selected_course_update]

                st.subheader("Update and Delete Course Assignment")
                with st.form("Update and Delete Course Assignment", clear_on_submit=True):
                
                    col1, col2 = st.columns(2)
                    
                    selected_year_update = col1.selectbox("Select Year:", year_levels, key="syu")
                    selected_semester_update = col2.selectbox("Select Semester:", semesters, key="sem")

                    col1, col2 = st.columns(2)
                    with col1:
                        update = st.form_submit_button("Update")
                        if update:
                            if all([selected_student_id, selected_course_code, selected_year_update, selected_semester_update]):
                                updateCourseAssignment(selected_student_id, selected_course_code, selected_year_update, selected_semester_update)
                                st.session_state.operation_success = "Data updated successfully."
                                st.experimental_rerun()
                            else:
                                st.warning("Please fill out all required fields.")
                                st.experimental_rerun()
                    
                    with col2:
                        deleted = st.form_submit_button("Delete")
                        if deleted:
                            if all([selected_student_id, selected_course_code]):
                                @st.experimental_dialog("Confirm DeletionCourse")
                                def confirm_deletioncourse_dialog():
                                    st.write(f"Are you sure you want to delete this course assignment? {selected_student_id} - {selected_course_update}")
                                    if st.button("Yes"):
                                        deleteCourseAssignment(selected_student_id, selected_course_code)
                                        st.session_state.operation_success = "Course Assignment deleted successfully."
                                        st.experimental_dialog()
                                        st.experimental_rerun()
                                    elif st.button("No"):
                                        st.experimental_dialog()
                                        st.experimental_rerun()

                                confirm_deletioncourse_dialog()

            # Check if operation success message is set
            if st.session_state.get("operation_success"):
                st.success(st.session_state.operation_success)
                st.session_state.operation_success = None

    # Course Directory Page
    elif selected == "Course Directory":
        st.header("Search by Student")

        student_names_list = [""] + list(student_names.values())  # Add a blank option
        selected_student_name = st.selectbox("Select Student:", student_names_list)

        if selected_student_name:
            selected_student_id = next(key for key, value in student_names.items() if value == selected_student_name)
            st.write(f"Selected Student: {selected_student_name}")

            # Calculate fixed_total_units from the sum of units in the prospectus table
            fixed_total_units_df = pd.read_sql_query(
                "SELECT SUM(Units) as TotalUnits FROM prospectus", 
                conn
            )
            fixed_total_units = fixed_total_units_df['TotalUnits'].iloc[0]

            total_units_df = pd.read_sql_query(
                "SELECT ca.StudentID, ca.CourseCode, p.CourseDesc, p.Units "
                "FROM courseassignment ca "
                "JOIN prospectus p ON ca.CourseCode = p.CourseCode "
                "WHERE ca.StudentID = ?",  # Only count courses for the selected student
                conn, params=(selected_student_id,)
            )
            if not total_units_df.empty:
                total_units = total_units_df['Units'].sum()
                # Data for the pie chart
                data = {
                    'Category': ['Units Taken', 'Units Remaining'],
                    'Units': [total_units, fixed_total_units - total_units]
                }

                # Create a pie chart using Plotly
                fig = px.pie(data, names='Category', values='Units', title='Total Units Distribution')

                # Display the pie chart in Streamlit
                st.plotly_chart(fig)

                st.write(f"Total Units for {selected_student_name}: {total_units}")
            else:
                st.warning("No course assignments found for the selected student.")

            df = pd.read_sql_query(
                "SELECT ca.StudentID, ca.CourseCode, p.CourseDesc, ca.Semester, ca.YearLevel, p.Units "
                "FROM courseassignment ca "
                "JOIN prospectus p ON ca.CourseCode = p.CourseCode "
                "WHERE ca.StudentID = ? "
                "ORDER BY ca.YearLevel DESC, ca.Semester DESC", 
                conn, params=(selected_student_id,)
            )

            if not df.empty:
                for year in year_levels:
                    for sem in semesters:
                        filtered_df = df[(df['YearLevel'] == year) & (df['Semester'] == sem)]
                        if not filtered_df.empty:
                            st.write(f"{year} YearLevel - {sem}")
                            # Drop the columns StudentID, YearLevel, and Semester before displaying
                            display_df = filtered_df.drop(columns=['StudentID', 'YearLevel', 'Semester'])
                            st.dataframe(display_df)
        else:
            st.header("Course Count by Semester and Year Level")

            count_df = pd.read_sql_query(
                "SELECT AcademicYear, Semester, CourseCode, COUNT(*) as Count "
                "FROM courseassignment "
                "WHERE AcademicYear IS NOT NULL "
                "GROUP BY AcademicYear, Semester, CourseCode", 
                conn
            )

            # Get unique combinations of AcademicYear and Semester
            unique_combinations = count_df[['AcademicYear', 'Semester']].drop_duplicates()

            for _, row in unique_combinations.iterrows():
                acad_year = row['AcademicYear']
                semester = row['Semester']

                # Filter data for the current combination
                filtered_df = count_df[(count_df['AcademicYear'] == acad_year) & 
                                    (count_df['Semester'] == semester)]

                # Create a bar chart
                fig = px.bar(
                    filtered_df,
                    x='CourseCode',
                    y='Count',
                    barmode='group',
                    labels={
                        'CourseCode': 'Course Code',
                        'Count': 'Count'
                    },
                    title=f"Count of Courses - Academic Year: {acad_year}, Semester: {semester}"
                )

                # Display the chart
                st.plotly_chart(fig)