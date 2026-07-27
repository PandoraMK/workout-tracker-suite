import datetime
import json
import os
from openpyxl import Workbook, load_workbook
import pandas as pd
import streamlit as st

# --- Load User Profile First (Required for st.set_page_config) ---
user_profile_file = "user_profile.json"
default_profile = {
    "name": "Modiri",
    "body_weight": 88.0,
    "gender": "Male",
    "age": 25,
    "height": 178.0,
}

if os.path.exists(user_profile_file):
  try:
    with open(user_profile_file, "r") as f:
      loaded_profile = json.load(f)
      default_profile.update(loaded_profile)
  except:
    pass

current_user = default_profile.get("name", "Modiri")

# Now set page config dynamically using the user's name
st.set_page_config(
    page_title=f"{current_user}'s Workout Master Suite",
    page_icon="💪",
    layout="centered",
)
