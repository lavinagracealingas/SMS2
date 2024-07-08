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
    def createStudent():
        cur.execute(
            """CREATE TABLE IF NOT EXISTS student (
            StudentID TEXT NOT NULL UNIQUE,
            Name TEXT NOT NULL,
            BirthDate TEXT NOT NULL,
            Sex TEXT NOT NULL,
            Gender TEXT NOT NULL,
            Religion TEXT NOT NULL,
            Address TEXT NOT NULL,
            Track TEXT NOT NULL,
            Program TEXT NOT NULL,
            ContactNumber TEXT NOT NULL,
            PRIMARY KEY(StudentID))"""
        )
        conn.commit()

    # Function definitions
    def addStudent(StudentID, Name, BirthDate, Sex, Gender, Religion, Address, Track, Program, ContactNumber):
        # Check if StudentID already exists
        cur.execute("SELECT StudentID FROM student WHERE StudentID=?", (StudentID,))
        if cur.fetchone():
            st.warning("A student with this ID already exists.")
            return False
        cur.execute(
            "INSERT INTO student (StudentID, Name, BirthDate, Sex, Gender, Religion, Address, Track, Program, ContactNumber) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (StudentID, Name, BirthDate, Sex, Gender, Religion, Address, Track, Program, ContactNumber))
        conn.commit()
        return True

    def updateStudent(StudentID, Name, BirthDate, Sex, Gender, Religion, Address, Track, Program, ContactNumber):
        cur.execute("SELECT StudentID FROM student WHERE StudentID=?", (StudentID,))
        if cur.fetchone() is None:
            st.warning("Student ID not found.")
            return False
        cur.execute(
            "UPDATE student SET Name=?, BirthDate=?, Sex=?, Gender=?, Religion=?, Address=?, Track=?, Program=?, ContactNumber=? WHERE StudentID=?",
            (Name, BirthDate, Sex, Gender, Religion, Address, Track, Program, ContactNumber, StudentID))
        conn.commit()
        return True

    def deleteStudent(StudentID):
        cur.execute("SELECT StudentID FROM student WHERE StudentID=?", (StudentID,))
        if cur.fetchone() is None:
            st.warning("Student ID not found.")
            return False
        cur.execute("DELETE FROM student WHERE StudentID=?", (StudentID,))
        conn.commit()
        return True

    def get_students_by_semester_year(semester, year_level):
        cur.execute("SELECT * FROM academicrecords WHERE Semester=? AND YearLevel=?", (semester, year_level))
        return cur.fetchall()


    def get_student_details(StudentID):
        cur.execute("SELECT * FROM student WHERE StudentID=?", (StudentID,))
        return cur.fetchone()
        

    # Set up session state to store operation success
    if 'operation_success' not in st.session_state:
        st.session_state.operation_success = None
    if 'delete_confirm' not in st.session_state:
        st.session_state.delete_confirm = False
    if 'student_to_delete' not in st.session_state:
        st.session_state.student_to_delete = None

    # Constants
    religion_list = ["Roman Catholic", "Islam", "Christian", "Others"]
    region_list = ["Zamboanga Peninsula (Region IX)", "Northern Mindanao (Region X)", "Davao Region (XI)", "Soccsksargen (Region XII)", "Caraga (Region XIII)", "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)", "Others"]
    yrlvl_list = ["1", "2", "3", "4"]
    sex_list = ["Female", "Male"]
    gender_list = ["Female", "Male", "LGBTQIA+"]
    program_list = ["BS Statistics", "BS Mathematics"]
    track_list = ["Science, Technology, Engineering, and Mathematics (STEM)", "Accountancy, Business and Management (ABM)", "Humanities and Social Sciences (HUMSS)", "General Academic Strand (GAS)", "Technical-Vocational-Livelihood (TVL)"]

    # Navigation
    selected = option_menu(
        menu_title=None,
        options=["Student Registration", "Academic Records", "Student Directory"],
        icons=["person-circle", "folder-fill"],
        orientation="horizontal",
    )
    if selected == "Student Registration":
        if st.session_state.operation_success:
            st.success(st.session_state.operation_success)
            st.session_state.operation_success = None  # Reset the flag

        # Student Registration
        st.header("Demographics")

        # Fetch all students for selection
        cur.execute("SELECT StudentID, Name FROM student")
        students = cur.fetchall()
        # Sort students alphabetically based on the last word of their name
        sorted_students = sorted(students, key=lambda x: x[1].split()[-1])

        # Create a dictionary for mapping student name to ID
        student_dict = {name: sid for sid, name in sorted_students}

        # Selection box for existing students
        selected_student_name = st.selectbox("Select Student to Update", options=[""] + list(student_dict.keys()))
        student_details = get_student_details(student_dict[selected_student_name]) if selected_student_name else None

        with st.form("entry_form", clear_on_submit=True):
            idnum = st.text_input("ID Number", placeholder="####-####", value=student_details[0] if student_details else "")
            name = st.text_input("Name", placeholder="Sana Minatozaki", value=student_details[1] if student_details else "")
            BirthDate = st.text_input("BirthDate", placeholder="August 7, 2002", value=student_details[2] if student_details else "")

            col1, col2, col3 = st.columns(3)
            sex = col1.selectbox("Sex", sex_list, index=sex_list.index(student_details[3]) if student_details else 0)
            gender = col2.selectbox("Gender", gender_list, index=gender_list.index(student_details[4]) if student_details else 0)
            religion = col3.selectbox("Religious Affiliation", religion_list, index=religion_list.index(student_details[5]) if student_details else 0)

            address = student_details[6].split(",") if student_details else ["", "", "", ""]
            region = st.selectbox("Region", region_list, index=region_list.index(address[0]) if student_details else 0)
            province = st.text_input("Province", placeholder="Lanao del Norte", value=address[1] if student_details else "")
            city = st.text_input("City", placeholder="Iligan", value=address[2] if student_details else "")
            barangay = st.text_input("Barangay", placeholder="Tibanga", value=address[3] if student_details else "")

            track = st.selectbox("Academic Track/Strand", track_list, index=track_list.index(student_details[7]) if student_details else 0)

            col1, col2= st.columns(2)
            prog = col1.selectbox("Program", program_list, index=program_list.index(student_details[8]) if student_details else 0)
            with col2:
                number = st.text_input("Phone Number", placeholder="09#########", value=student_details[9] if student_details else "")

            "---"

            col1, col2, col3 = st.columns(3)
            with col1:
                submitted = st.form_submit_button("Register")
                if submitted:
                    if all([idnum, name, BirthDate, sex, gender, religion, region, province, city, barangay, track, prog, number]):
                        success = addStudent(idnum, name, BirthDate, sex, gender, religion, region + "," + province + "," + city + "," + barangay, track, prog, number)
                        if success:
                            st.session_state.operation_success = "Student registered successfully."
                            st.rerun()
                    else:
                        st.warning("Please fill out all required fields.")

            with col2:
                updated = st.form_submit_button("Update")
                if updated and student_details:
                    if all([idnum, name, BirthDate, sex, gender, religion, region, province, city, barangay, track, prog, number]):
                        success = updateStudent(idnum, name, BirthDate, sex, gender, religion, region + "," + province + "," + city + "," + barangay, track, prog, number)
                        if success:
                            st.session_state.operation_success = "Student updated successfully."
                            st.rerun()
                    else:
                        st.warning("Please fill out all required fields.")

            with col3:
                deleted = st.form_submit_button("Delete")
                if deleted:
                    if all([idnum, name, BirthDate, sex, gender, religion, region, province, city, barangay, track, prog, number]):
                        @st.experimental_dialog("Confirm Deletion")
                        def confirm_deletion_dialog():
                            st.write(f"Are you sure you want to delete the student: {selected_student_name}?")
                            if st.button("Yes"):
                                deleteStudent(idnum)
                                st.session_state.operation_success = f"Student {selected_student_name} deleted successfully."
                                st.experimental_rerun()
                            elif st.button("No"):
                                st.experimental_rerun()
                        
                        confirm_deletion_dialog()
                    else:
                        st.warning("Please fill out all required fields.")



                if st.session_state.get("operation_success"):
                    st.success(st.session_state.operation_success)
                    st.session_state.operation_success = None

                        
# --------------------------------------------------------- #
    elif selected == "Academic Records":
        # Function to create academic records
        def createAcademicRecords(StudentID, YearLevel, Semester, ScholasticStatus, ScholarshipStatus):
            # Create the academicrecords table if it doesn't exist
            cur.execute(
                """CREATE TABLE IF NOT EXISTS academicrecords (
                RecordID INTEGER PRIMARY KEY AUTOINCREMENT,
                StudentID TEXT NOT NULL,
                ScholasticStatus TEXT NOT NULL,
                ScholarshipStatus TEXT,
                YearLevel INTEGER NOT NULL,
                Semester TEXT NOT NULL,
                UNIQUE(StudentID, YearLevel, Semester),
                FOREIGN KEY(StudentID) REFERENCES student(StudentID)
                )"""
            )
            
            # Check if the record already exists for the given StudentID
            cur.execute(
                "SELECT * FROM academicrecords WHERE StudentID = ? AND YearLevel = ? AND Semester = ?",
                (StudentID, YearLevel, Semester)
            )
            if cur.fetchone() is None:
                # If no record exists, insert the new academic record
                cur.execute(
                    "INSERT INTO academicrecords (StudentID, ScholasticStatus, ScholarshipStatus, YearLevel, Semester) VALUES (?, ?, ?, ?, ?)",
                    (StudentID, ScholasticStatus, ScholarshipStatus, YearLevel, Semester)
                )
                conn.commit()
                return True
            return False
        
        # Function to delete academic record
        def deleteAcademicRecords(StudentID):
            try:
                # Adjust your SQL DELETE query based on your database schema
                cur.execute("DELETE FROM academicrecords WHERE StudentID=?", (StudentID,))
                conn.commit()
                return True
            except Exception as e:
                st.error(f"Failed to delete academic records: {str(e)}")
                conn.rollback()
                return False


        def get_academic_record_details(StudentID):
            cur.execute("SELECT * FROM academicrecords WHERE StudentID=?", (StudentID,))
            return cur.fetchone()
            

        # Function to update academic record
        def updateAcademicRecords(StudentID, YearLevel, Semester, ScholasticStatus, ScholarshipStatus):
            try:
                # Check if the academic record exists for the given student, year level, and semester
                cur.execute("SELECT StudentID FROM academicrecords WHERE StudentID=? AND YearLevel=? AND Semester=?",
                            (StudentID, YearLevel, Semester))
                if cur.fetchone() is None:
                    st.warning("Academic record not found for the student, year level, and semester.")
                    return False
                
                # Update the academic record
                cur.execute(
                    """UPDATE academicrecords 
                    SET ScholasticStatus=?, ScholarshipStatus=?
                    WHERE StudentID=? AND YearLevel=? AND Semester=?""",
                    (ScholasticStatus, ScholarshipStatus, StudentID, YearLevel, Semester)
                )
                
                conn.commit()                    
                return True  # Return True to indicate success
                
            except Exception as e:
                # Handle any exceptions (e.g., SQL errors, database connection issues)
                print(f"Error updating academic records: {str(e)}")
                conn.rollback()  # Rollback changes if an error occurs
                return False


        if 'operation_success' not in st.session_state:
            st.session_state.operation_success = None
        if 'delete_confirmation' not in st.session_state:
            st.session_state.delete_confirmation = False

        # Settings
        scholastic_status = ["Regular", "Irregular"]
        year_level = ["1", "2", "3", "4"]
        semester = ["1st Term", "2nd Term", "Summer Term"]

        # Fetching student IDs and names
        cur.execute("SELECT StudentID, Name FROM student")
        students = cur.fetchall()
        student_ids = [student[0] for student in students]
        student_names = {student[0]: student[1] for student in students}  # Dictionary for mapping StudentID to StudentName

        # Academic Record Page
        if selected == "Academic Records":
            sub_selected = option_menu(
                menu_title=None,
                options=["Assign", "Manage"],
                orientation="vertical",
                default_index=0
            )

            if sub_selected == "Assign":
                st.header("Assign")
                
                # Fetch all students for selection
                cur.execute("SELECT StudentID, Name FROM student")
                students = cur.fetchall()
                # Sort students alphabetically based on the last word of their name
                sorted_students = sorted(students, key=lambda x: x[1].split()[-1])
                student_dict = {name: sid for sid, name in sorted_students}

            
                with st.form("Assign", clear_on_submit=True):
                    selected_student_name = st.selectbox("Select Student", options=[""] + list(student_dict.keys()))
                    "---"
                    col1, col2 = st.columns(2)
                    selected_year = col1.selectbox("Select Year Level:", year_level, key="year")
                    selected_semester = col2.selectbox("Select Semester:", semester, key="sem")

                    col1, col2 = st.columns(2)
                    scholastic_status = col1.selectbox("Scholastic Status:", scholastic_status)
                    with col2:
                        scholarship = st.text_input("Scholarship Status", placeholder="DOST")
                    
                    "---"

                    submitted = st.form_submit_button("Register")
                    if submitted:
                        success_count = 0
                        if all([selected_student_name, selected_year, selected_semester, scholastic_status, scholarship]):
                            student_id = student_dict[selected_student_name]
                            success = createAcademicRecords(student_id, selected_year, selected_semester, scholastic_status, scholarship)
                            if success:
                                success_count += 1
                            if success_count > 0:
                                st.success(f'{success_count} academic record(s) have been successfully added.')
                            else:
                                st.warning('Academic record already exists for this combination.')
                        else:
                            st.warning("Please fill out all required fields.")

            elif sub_selected == "Manage":
                st.header("Manage Academic Records")

                # Fetching student IDs and names
                cur.execute("SELECT StudentID, Name FROM student")
                students = cur.fetchall()
                # Sort students alphabetically based on the last word of their name
                sorted_students = sorted(students, key=lambda x: x[1].split()[-1])
                student_dict = {name: sid for sid, name in sorted_students}

                # Selection box for existing students
                selected_student_name = st.selectbox("Select Student to Update", options=[""] + list(student_dict.keys()))
                selected_year_level = None
                selected_semester = None

                if selected_student_name:
                    selected_student_id = student_dict[selected_student_name]

                    # Fetch year levels and semesters for the selected student
                    cur.execute("""
                        SELECT DISTINCT ar.YearLevel, ar.Semester 
                        FROM academicrecords ar 
                        WHERE ar.StudentID = ? 
                        ORDER BY ar.YearLevel, ar.Semester
                    """, (selected_student_id,))
                    levels_and_semesters = cur.fetchall()

                    if not levels_and_semesters:
                        st.warning(f"No academic records found for {selected_student_name}.")
                    else:
                        year_levels = sorted(set([ls[0] for ls in levels_and_semesters]), reverse=True)
                        semesters = sorted(set([ls[1] for ls in levels_and_semesters]))

                        col1, col2 = st.columns(2)
                        selected_year_level = col1.selectbox("Select Year Level:", [""] + year_levels)
                        selected_semester = col2.selectbox("Select Semester:", [""] + semesters)

                scholastic_status_value = ""
                scholarship_value = ""

                if selected_student_name and selected_year_level and selected_semester:
                    selected_student_id = student_dict[selected_student_name]

                    # Fetch the academic record for the selected student, year level, and semester
                    cur.execute("""
                        SELECT ar.ScholasticStatus, ar.ScholarshipStatus 
                        FROM academicrecords ar 
                        WHERE ar.StudentID = ? AND ar.YearLevel = ? AND ar.Semester = ?
                    """, (selected_student_id, selected_year_level, selected_semester))

                    record = cur.fetchone()
                    if record:
                        scholastic_status_value = record[0]
                        scholarship_value = record[1]

                with st.form("Update and Delete Academic Record", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    if selected_student_name and selected_year_level and selected_semester:
                        updated_scholastic_status = col1.selectbox("Scholastic Status:", scholastic_status, index=scholastic_status.index(scholastic_status_value) if scholastic_status_value else 0)
                        updated_scholarship_status = col2.text_input("Scholarship Status", value=scholarship_value)
                    else:
                        updated_scholastic_status = col1.selectbox("Scholastic Status:", [""])
                        updated_scholarship_status = col2.text_input("Scholarship Status", value="")
                    col1, col2 = st.columns(2)
                    with col1:
                        update = st.form_submit_button("Update")
                        if update:
                            if selected_student_name and selected_student_id and selected_year_level and selected_semester:
                                # Perform update operation
                                update_success = updateAcademicRecords(selected_student_id, selected_year_level, selected_semester, updated_scholastic_status, updated_scholarship_status)
                                if update_success:
                                    st.session_state.operation_success = "Academic record updated successfully."
                                else:
                                    st.warning("Failed to update academic record.")
                            else:
                                st.warning("Please fill out all required fields.")



                # Check if operation success message is set
                if st.session_state.get("operation_success"):
                    st.success(st.session_state.operation_success)
                    st.session_state.operation_success = None


# -----------------------------------------------------
        # Student Directory
    elif selected == "Student Directory":
        st.header("Student Record")


        # Fetching student IDs and names
        cur.execute("SELECT StudentID, Name FROM student")
        students = cur.fetchall()
        # Sort students alphabetically based on the last word of their name
        sorted_students = sorted(students, key=lambda x: x[1].split()[-1])

        # Create a dictionary for mapping student name to ID
        student_dict = {name: sid for sid, name in sorted_students}

        # Selection box for existing students
        selected_student_name = st.selectbox("Select Student to Update", options=[""] + list(student_dict.keys()))

        if selected_student_name:
            selected_student_id = student_dict[selected_student_name]

            # Fetch and display student details
            student_details = get_student_details(selected_student_id)
            if student_details:
                st.write(f"**Name:** {student_details[1]}")
                st.write(f"**ID Number:** {student_details[0]}")
                st.write(f"**BirthDate:** {student_details[2]}")
                st.write(f"**Sex:** {student_details[3]}")
                st.write(f"**Gender:** {student_details[4]}")
                st.write(f"**Religion:** {student_details[5]}")
                st.write(f"**Address:** {student_details[6]}")
                st.write(f"**Track:** {student_details[7]}")
                st.write(f"**Program:** {student_details[8]}")
                st.write(f"**Phone Number:** {student_details[9]}")

            # Fetch the academic records for the selected student
            assignments = pd.read_sql_query(
                "SELECT ar.YearLevel, ar.Semester, ar.ScholasticStatus, ar.ScholarshipStatus "
                "FROM academicrecords ar "
                "WHERE ar.StudentID = ? "
                "ORDER BY ar.YearLevel AND ar.Semester", conn, params=(selected_student_id,)
            )

            if not assignments.empty:
                # Group by Year Level and Semester
                grouped_records = assignments.groupby(['YearLevel', 'Semester'])
                for (year_level, semester), group in grouped_records:
                    st.markdown(f"**Year Level {year_level} - {semester}**")
                    st.dataframe(group)   
            else:
                st.warning(f"No academic records found for {selected_student_name}.")
        else:
            all_assignments = pd.read_sql_query(
                "SELECT s.StudentID, s.Name, s.Sex, s.Gender, s.Religion, s.Address, s.Track, s.Program, ar.ScholasticStatus, ar.ScholarshipStatus, s.ContactNumber, ar.Semester, ar.YearLevel,     ROW_NUMBER() OVER(PARTITION BY ar.YearLevel, ar.Semester ORDER BY ar.YearLevel, ar.Semester) AS SemesterSequence "
                "FROM academicrecords ar "
                "JOIN student s ON ar.StudentID = s.StudentID "  # Correct join condition
                "ORDER BY ar.YearLevel, ar.Semester", conn
            )

            if not all_assignments.empty:
                # Group by Year Level and Semester
                grouped_all_records = all_assignments.groupby(['YearLevel', 'Semester'])
                for (year_level, semester), group in grouped_all_records:
                    st.markdown(f"**Year Level {year_level} - {semester}**")
                    total_students = group.shape[0]  # Number of rows in the dataframe
                    st.write(f"Total number of students: {total_students}")
                    st.dataframe(group)
            else:
                st.warning("No academic records found.")