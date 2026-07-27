import datetime
import json
import os
from openpyxl import Workbook, load_workbook
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Your Personal Workout Master Suite", page_icon="💪", layout="centered"
)

file_path = "Workout_Master_Suite.xlsx"


def create_default_workbook(path):
  wb = Workbook()
  ws = wb.active
  ws.title = "Workout Log"

  ws.append([])
  ws.append([])
  ws.append([])

  headers = [
      "Date",
      "Routine / Focus",
      "Exercise",
      "Sets",
      "Reps",
      "Weight (kg)",
      "Total Volume (kg)",
      "RPE (1-10)",
  ]
  ws.append(headers)
  wb.save(path)


if not os.path.exists(file_path):
  create_default_workbook(file_path)

# --- Persistent User Profile Setup ---
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

if "user_profile" not in st.session_state:
  st.session_state.user_profile = default_profile

# Sidebar for User Profile & Settings
with st.sidebar:
  st.markdown("### ⚙️ Athlete Profile")
  p = st.session_state.user_profile

  entered_name = st.text_input("Name", value=p.get("name", "Modiri"))
  entered_bw = st.number_input(
      "Body Weight (kg)",
      min_value=30.0,
      max_value=250.0,
      value=float(p.get("body_weight", 88.0)),
      step=0.5,
  )
  entered_gender = st.selectbox(
      "Gender",
      ["Male", "Female", "Other"],
      index=(
          0
          if p.get("gender", "Male") == "Male"
          else (1 if p.get("gender") == "Female" else 2)
      ),
  )
  entered_age = st.number_input(
      "Age", min_value=10, max_value=100, value=int(p.get("age", 25))
  )
  entered_height = st.number_input(
      "Height (cm)",
      min_value=60.0,
      max_value=250.0,
      value=float(p.get("height", 178.0)),
      step=1.0,
  )

  if st.button("Save Profile"):
    st.session_state.user_profile = {
        "name": entered_name,
        "body_weight": entered_bw,
        "gender": entered_gender,
        "age": entered_age,
        "height": entered_height,
    }
    try:
      with open(user_profile_file, "w") as f:
        json.dump(st.session_state.user_profile, f)
    except:
      pass
    st.success("Profile saved successfully!")

current_user = st.session_state.user_profile.get("name", "Modiri")

st.title(f"💪 {current_user}'s Workout Master Suite")
st.write(
    f"Elite training tracker for **{current_user}** (BW:"
    f" {st.session_state.user_profile.get('body_weight')}kg) built with dynamic"
    " weight progressions & analytics."
)

# Navigation Tabs for enhanced structure
tab1, tab2, tab3 = st.tabs(
    [
        "📝 Logger Form",
        "📈 Progress & Analytics",
        "📖 Glossary & Definitions",
    ]
)

with tab1:
  st.subheader("Add Exercise Details")

  routine_exercises_map = {
      "Upper Body A": [
          "Barbell Bench Press",
          "Incline DB Press",
          "Overhead Shoulder Press",
          "Cable Lateral Raises",
          "DB Lateral Raises",
          "Tricep Pushdowns",
      ],
      "Upper Body B": [
          "Lat Pulldown",
          "Seated Cable Row",
          "Neutral Grip Pull-Ups",
          "Barbell Bent-Over Row",
          "Face Pulls",
          "Rear Delt Fly",
      ],
      "Lower Body A": [
          "Barbell Back Squat",
          "Leg Press",
          "Romanian Deadlift",
          "Standing Calf Raises",
      ],
      "Lower Body B": [
          "Bulgarian Split Squat",
          "Goblet Squat",
          "Romanian Deadlift",
          "Leg Press",
      ],
      "Cardio": ["Indoor Treadmill Run", "Assault Bike"],
      "Full Body": [
          "Barbell Back Squat",
          "Barbell Bench Press",
          "Lat Pulldown",
          "Standing Calf Raises",
      ],
  }

  col1, col2 = st.columns(2)
  with col1:
    routine_options = list(routine_exercises_map.keys()) + ["Custom"]
    routine = st.selectbox("Routine / Focus", routine_options)

    if routine == "Custom":
      routine_name = st.text_input("Enter custom routine name", "Custom Focus")
      available_exercises = [
          "Barbell Back Squat",
          "Barbell Bench Press",
          "Lat Pulldown",
      ]
    else:
      routine_name = routine
      available_exercises = routine_exercises_map.get(routine, [])

  with col2:
    exercise_choice = st.selectbox(
        "Select Exercise for Routine", available_exercises + ["Other (Type Below)"]
    )
    if exercise_choice == "Other (Type Below)":
      exercise_name = st.text_input("Type Exercise Name", "New Exercise")
    else:
      exercise_name = exercise_choice

  st.markdown("---")
  st.write("🏋️ **Set & Weight Progression (Pyramids / Weight Changes)**")

  num_blocks = st.selectbox(
      "How many different weight blocks?",
      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      index=0,
  )

  total_sets = 0
  total_volume = 0
  weight_parts = []
  representative_reps = 8

  for i in range(num_blocks):
    if num_blocks > 1:
      st.caption(f"Block {i+1}")

    c1, c2, c3 = st.columns(3)
    with c1:
      s = st.number_input(
          f"Sets ({i+1})",
          min_value=1,
          max_value=20,
          value=2 if i > 0 else 4,
          key=f"sets_{i}",
      )
    with c2:
      r = st.number_input(
          f"Reps ({i+1})",
          min_value=1,
          max_value=100,
          value=8,
          key=f"reps_{i}",
      )
    with c3:
      w = st.number_input(
          f"Weight kg ({i+1})",
          min_value=0.0,
          max_value=500.0,
          value=40.0 + (i * 5.0),
          step=2.5,
          key=f"weight_{i}",
      )

    total_sets += s
    if i == 0:
      representative_reps = r

    total_volume += s * r * w
    weight_parts.append(f"{w}kg")

  if len(weight_parts) == 1:
    weight_str = weight_parts[0]
  elif len(weight_parts) == 2:
    weight_str = f"{weight_parts[0]} & {weight_parts[1]}"
  else:
    weight_str = ", ".join(weight_parts[:-1]) + f" & {weight_parts[-1]}"

  st.info(
      f"📊 **Calculated Summary:** Total Sets: **{total_sets}** | Combined"
      f" Weight: **{weight_str}** | Total Volume: **{total_volume} kg**"
  )

  st.markdown("---")
  col_rpe, col_date = st.columns(2)
  with col_rpe:
    rpe = st.slider(
        "RPE (1-10)", min_value=1.0, max_value=10.0, value=8.0, step=0.5
    )
  with col_date:
    log_date = st.date_input("Workout Date", datetime.date.today())

  if st.button("Save Structured Entry to Excel"):
    try:
      wb = load_workbook(file_path)
      if "Workout Log" in wb.sheetnames:
        ws = wb["Workout Log"]
        next_row = ws.max_row + 1

        date_str = log_date.strftime("%Y/%m/%d")
        total_volume_str = f"{total_volume}kg"

        ws.cell(row=next_row, column=1, value=date_str)
        ws.cell(row=next_row, column=2, value=routine_name)
        ws.cell(row=next_row, column=3, value=exercise_name)
        ws.cell(row=next_row, column=4, value=total_sets)
        ws.cell(row=next_row, column=5, value=representative_reps)
        ws.cell(row=next_row, column=6, value=weight_str)
        ws.cell(row=next_row, column=7, value=total_volume_str)
        ws.cell(row=next_row, column=8, value=rpe)

        wb.save(file_path)
        st.success(
            f"Successfully logged {exercise_name} ({weight_str}) under"
            f" {routine_name}!"
        )
      else:
        st.error("'Workout Log' sheet not found.")
    except Exception as e:
      st.error(f"Error saving to Excel: {e}")

  st.markdown("---")
  st.subheader("📊 Live Workout Log Preview")
  try:
    if os.path.exists(file_path):
      df_log = pd.read_excel(file_path, sheet_name="Workout Log", skiprows=3)
      if not df_log.empty:
        st.dataframe(df_log.tail(6), use_container_width=True)
      else:
        st.info("No workout entries logged yet.")
  except Exception as e:
    st.info(f"Could not load log preview: {e}")

with tab2:
  st.subheader("📈 Training Analytics & Progress Charts")
  try:
    if os.path.exists(file_path):
      df_analytics = pd.read_excel(
          file_path, sheet_name="Workout Log", skiprows=3
      )
      if not df_analytics.empty and "Total Volume (kg)" in df_analytics.columns:
        df_analytics["Clean_Volume"] = (
            df_analytics["Total Volume (kg)"]
            .astype(str)
            .str.replace("kg", "", regex=False)
            .astype(float)
        )

        st.markdown("### Total Volume Lifted Over Time")
        chart_data = df_analytics[["Date", "Clean_Volume"]].dropna()
        if not chart_data.empty:
          st.line_chart(
              chart_data.set_index("Date"), use_container_width=True
          )
        else:
          st.info("Log a few workouts to see your volume progression chart!")

        st.markdown("---")
        st.markdown("### Filter History by Routine / Focus")
        df_analytics["Routine / Focus"] = df_analytics[
            "Routine / Focus"
        ].fillna("Unassigned")
        unique_routines = sorted(
            df_analytics["Routine / Focus"].unique().tolist()
        )
        selected_routine = st.selectbox(
            "Select Routine to Inspect", unique_routines, key="analytics_routine"
        )
        filtered_df = df_analytics[
            df_analytics["Routine / Focus"] == selected_routine
        ]
        st.dataframe(filtered_df, use_container_width=True)
      else:
        st.info("Add entries to generate performance charts.")
    else:
      st.info("Workout file not found.")
  except Exception as e:
    st.info(f"Error loading charts: {e}")

with tab3:
  st.subheader("📖 Fitness Glossary & Terminology Guide")
  st.markdown("""
    * **RPE (Rate of Perceived Exertion):** A scale from **1 to 10** used to measure how intense a set felt relative to failure.
      * *10:* Absolute maximum effort (0 reps left in the tank).
      * *8 - 9:* Hard set; you could have realistically done 1 or 2 more reps.
      * *6 - 7:* Moderate effort; comfortable with several reps left.
    * **Total Volume:** The overall workload calculated as $\text{Sets} \times \text{Reps} \times \text{Weight}$. Tracking volume over time is key for progressive overload and muscle hypertrophy.
    * **Pyramids / Weight Blocks:** Changing weights across sets within the same exercise (e.g., starting lighter for warm-up/higher reps, then increasing the weight for working sets).
    * **Routine / Focus:** The structural split of your training day (e.g., Upper Body A/B, Lower Body A/B) ensuring balanced muscle recovery and growth.
    """)
