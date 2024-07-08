import pickle
from pathlib import Path
import streamlit as st
import streamlit_authenticator as stauth

names = ["Johniel Babiera", "Daisy Polestico"]
usernames = ["jbabiera","dpolestico"]
passwords = ["abc123","def123"]

# Pass the list of passwords directly to the 
# Hasher constructor and generate the hashes
hashed_passwords = stauth.Hasher(passwords).generate()

file_path = Path(__file__).parent / "hashed_pw.pkl"
with file_path.open("wb") as file:
    pickle.dump(hashed_passwords, file)

