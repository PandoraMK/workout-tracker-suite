from datetime import datetime
import io
import os
import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE CONNECTION SETUP (Cloud Turso & Local SQLite Fallback) ---
try:
  import libsql

  db_url = st.secrets["TURSO_DATABASE_URL"]
  auth_token = st.secrets["TURSO_AUTH_TOKEN"]
  conn = libsql.connect(database=db_url, auth_token=auth_token)
  DB_MODE = "cloud"
except Exception:
  DB_FILE = "workout_master.db"
  conn = sqlite3.connect(DB_FILE, check_same_thread=False)
  DB_MODE = "local"


def init_db():
  if DB_MODE == "cloud":
    cursor = conn.cursor()
  else:
    local_conn = sqlite3.connect(DB_FILE)
    cursor = local_conn.cursor()

  # 1. Workouts Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            routine TEXT,
            exercise TEXT,
            sets INTEGER,
            reps INTEGER,
            weight TEXT,
            total_volume TEXT,
            rpe REAL
        )
    """)

  # 2. Reviews Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            tester_name TEXT,
            rating INTEGER,
            category TEXT,
            message TEXT
        )
    """)

  # 3. Body Weight Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS body_weight (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            body_weight REAL,
            notes TEXT
        )
    """)

  # 4. Profile Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            body_weight REAL,
            gender TEXT,
            age INTEGER,
            height REAL
        )
    """)

  # Insert default profile if not exists
  cursor.execute(
      """
        INSERT OR IGNORE INTO profile (id, name, body_weight, gender, age, height)
        VALUES (1, 'Modiri', 88.0, 'Male', 25, 178.0)
    """
  )

  if DB_MODE == "cloud":
    conn.commit()
  else:
    local_conn.commit()
    local_conn.close()


init_db()


def load_profile():
  if DB_MODE == "cloud":
    df = pd.read_sql_query(
        "SELECT name, body_weight, gender, age, height FROM profile WHERE id ="
        " 1",
        conn,
    )
    if not df.empty:
      return {
          "name": df["name"].iloc[0],
          "body_weight": float(df["body_weight"].iloc[0]),
          "gender": df["gender"].iloc[0],
          "age": int(df["age"].iloc[0]),
          "height": float(df["height"].iloc[0]),
      }
  else:
    local_conn = sqlite3.connect(DB_FILE)
    cursor = local_conn.cursor()
    cursor.execute(
        "SELECT name, body_weight, gender, age, height FROM profile WHERE id = 1"
    )
    row = cursor.fetchone()
    local_conn.close()
    if row:
      return {
          "name": row[0],
          "body_weight": row[1],
          "gender": row[2],
          "age": row[3],
          "height": row[4],
      }
  return {
      "name": "Modiri",
      "body_weight": 88.0,
      "gender": "Male",
      "age": 25,
      "height": 178.0,
  }


def save_profile_db(profile_data):
  if DB_MODE == "cloud":
    cursor = conn.cursor()
    cursor.execute(
        """
            UPDATE profile 
            SET name = ?, body_weight = ?, gender = ?, age = ?, height = ?
            WHERE id = 1
        """,
        (
            profile_data["name"],
            profile_data["body_weight"],
            profile_data["gender"],
            profile_data["age"],
            profile_data["height"],
        ),
    )
    conn.commit()
  else:
    local_conn = sqlite3.connect(DB_FILE)
    cursor = local_conn.cursor()
    cursor.execute(
        """
            UPDATE profile 
            SET name = ?, body_weight = ?, gender = ?, age = ?, height = ?
            WHERE id = 1
        """,
        (
            profile_data["name"],
            profile_data["body_weight"],
            profile_data["gender"],
            profile_data["age"],
            profile_data["height"],
        ),
    )
    local_conn.commit()
    local_conn.close()


if "user_profile" not in st.session_state:
  st.session_state.user_profile = load_profile()

current_user = st.session_state.user_profile.get("name", "Modiri")

st.set_page_config(
    page_title=f"{current_user}'s Workout Master Suite",
    page_icon="💪",
    layout="centered",
)

# --- SIDEBAR FOR USER PROFILE & SETTINGS ---
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
      min_value=100.0,
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
    save_profile_db(st.session_state.user_profile)
    st.success("Profile saved and synced across devices!")

  st.markdown("---")
  st.markdown("### 💾 Data Export")
  st.write(
      "Download a fresh Excel file containing all your latest synced logs."
  )

  try:
    if DB_MODE == "cloud":
      df_exp_workouts = pd.read_sql_query("SELECT * FROM workouts", conn)
      df_exp_bw = pd.read_sql_query("SELECT * FROM body_weight", conn)
      df_exp_reviews = pd.read_sql_query("SELECT * FROM reviews", conn)
      df_exp_profile = pd.read_sql_query("SELECT * FROM profile", conn)
    else:
      conn_export = sqlite3.connect(DB_FILE)
      df_exp_workouts = pd.read_sql_query(
          "SELECT * FROM workouts", conn_export
      )
      df_exp_bw = pd.read_sql_query("SELECT * FROM body_weight", conn_export)
      df_exp_reviews = pd.read_sql_query("SELECT * FROM reviews", conn_export)
      df_exp_profile = pd.read_sql_query("SELECT * FROM profile", conn_export)
      conn_export.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_exp_workouts.to_excel(writer, sheet_name="Workout Log", index=False)
      df_exp_bw.to_excel(writer, sheet_name="Body Weight Log", index=False)
      df_exp_reviews.to_excel(writer, sheet_name="Reviews", index=False)
      df_exp_profile.to_excel(writer, sheet_name="Profile", index=False)
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Download Excel Backup",
        data=excel_data,
        file_name="Workout_Master_Suite_Backup.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  except Exception as e:
    st.error(f"Could not prepare Excel download: {e}")

current_user = st.session_state.user_profile.get("name", "Modiri")

st.title(f"💪 {current_user}'s Workout Master Suite")
st.write(
    f"Elite training tracker for **{current_user}** (BW:"
    f" {st.session_state.user_profile.get('body_weight')}kg) with cloud"
    " multi-device sync & Excel backups."
)

# --- NAVIGATION TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📝 Logger Form",
        "⚖️ Body Weight Tracker",
        "📈 Progress & Analytics",
        "📖 Glossary & Definitions",
        "💬 Feedback & Reviews",
    ]
)

with tab1:
  st.subheader("Add Exercise / Activity Details")

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
      "Home Workouts": [
          "Standard Push-Ups",
          "Pike Push-Ups",
          "Bodyweight Squats",
          "Chair Bulgarian Split Squats",
          "Walking Lunges",
          "Glute Bridges",
          "Chair Dips",
          "Superman Back Extensions",
          "Plank Hold",
      ],
      "Cardio": [
          "Outside Running",
          "Indoor Treadmill Run",
          "Assault Bike",
          "Rowing Machine",
      ],
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
        "Select Exercise / Activity", available_exercises + ["Other (Type Below)"]
    )
    if exercise_choice == "Other (Type Below)":
      exercise_name = st.text_input("Type Exercise Name", "New Exercise")
    else:
      exercise_name = exercise_choice

  # --- TARGETED STRETCHING GUIDE ---
  st.markdown("---")
  with st.expander(
      f"🧘 View Recommended Stretches for: **{routine_name}**", expanded=False
  ):
    if "Upper" in routine_name:
      st.markdown("""
            * **Pre-Workout Dynamic Stretches:** Arm circles, band pull-aparts, torso twists.
            * **Post-Workout Static Stretches:** Cross-body shoulder stretch, overhead tricep stretch, doorway chest stretch.
            """)
    elif "Lower" in routine_name:
      st.markdown("""
            * **Pre-Workout Dynamic Stretches:** Leg swings, world's greatest stretch, bodyweight squat pries.
            * **Post-Workout Static Stretches:** Standing quad stretch, seated hamstring stretch, figure-4 glute stretch.
            """)
    elif "Cardio" in routine_name:
      st.markdown("""
            * **Pre-Workout Dynamic Stretches:** High knees, walking lunges with twist, ankle bounces.
            * **Post-Workout Static Stretches:** Wall calf stretch, hip flexor stretch, hamstring stretch.
            """)
    else:
      st.markdown("""
            * **Pre-Workout Dynamic Stretches:** Arm circles, leg swings, light bodyweight movements.
            * **Post-Workout Static Stretches:** Full body static stretches focusing on worked muscle groups.
            """)

  st.markdown("---")

  # --- DYNAMIC FORM: CARDIO VS WEIGHTS ---
  if routine == "Cardio":
    st.write("🏃 **Cardio Metrics**")
    c1, c2, c3 = st.columns(3)
    with c1:
      cardio_dist = st.number_input(
          "Distance (km)", min_value=0.1, max_value=100.0, value=5.0, step=0.1
      )
    with c2:
      cardio_time = st.number_input(
          "Duration (mins)", min_value=1, max_value=600, value=30, step=1
      )
    with c3:
      cardio_hr = st.number_input(
          "Avg Heart Rate (bpm)", min_value=0, max_value=220, value=145, step=1
      )

    if cardio_dist > 0:
      pace_mins = int(cardio_time // cardio_dist)
      pace_secs = int(((cardio_time / cardio_dist) - pace_mins) * 60)
      pace_str = f"{pace_mins}m {pace_secs}s / km"
    else:
      pace_str = "N/A"

    st.info(
        f"📊 **Cardio Summary:** Distance: **{cardio_dist} km** | Duration:"
        f" **{cardio_time} mins** | Pace: **{pace_str}** | HR:"
        f" **{cardio_hr if cardio_hr > 0 else 'N/A'} bpm**"
    )

    total_sets = 1
    representative_reps = cardio_time
    weight_str = f"{cardio_dist} km"
    total_volume_str = (
        f"HR: {cardio_hr}bpm" if cardio_hr > 0 else "N/A"
    )

  else:
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
            value=12 if routine == "Home Workouts" else 8,
            key=f"reps_{i}",
        )
      with c3:
        w = st.number_input(
            f"Weight kg ({i+1}) (0 for Bodyweight)",
            min_value=0.0,
            max_value=500.0,
            value=0.0 if routine == "Home Workouts" else 40.0 + (i * 5.0),
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

    total_volume_str = f"{total_volume}kg"

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
    log_date = st.date_input("Workout Date", datetime.today())

  if st.button("Save Structured Entry"):
    try:
      if DB_MODE == "cloud":
        cursor = conn.cursor()
      else:
        local_conn = sqlite3.connect(DB_FILE)
        cursor = local_conn.cursor()

      date_str = log_date.strftime("%Y/%m/%d")
      cursor.execute(
          """
                INSERT INTO workouts (date, routine, exercise, sets, reps, weight, total_volume, rpe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              date_str,
              routine_name,
              exercise_name,
              total_sets,
              representative_reps,
              weight_str,
              total_volume_str,
              rpe,
          ),
      )
      if DB_MODE == "cloud":
        conn.commit()
      else:
        local_conn.commit()
        local_conn.close()

      st.success(
          f"Successfully logged {exercise_name} ({weight_str}) under"
          f" {routine_name}!"
      )
      st.rerun()
    except Exception as e:
      st.error(f"Error saving entry: {e}")

  st.markdown("---")
  st.subheader("📊 Live Workout Log Preview")
  try:
    if DB_MODE == "cloud":
      df_log = pd.read_sql_query(
          "SELECT date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts ORDER BY id DESC",
          conn,
      )
    else:
      conn_prev = sqlite3.connect(DB_FILE)
      df_log = pd.read_sql_query(
          "SELECT date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts ORDER BY id DESC",
          conn_prev,
      )
      conn_prev.close()

    if not df_log.empty:
      st.dataframe(df_log.head(6), use_container_width=True)
    else:
      st.info("No workout entries logged yet.")
  except Exception as e:
    st.info(f"Could not load log preview: {e}")

with tab2:
  st.subheader("⚖️ Body Weight Tracker")
  st.write("Log your body weight regularly to track progress toward your goals.")

  with st.form("body_weight_form"):
    c1, c2 = st.columns(2)
    with c1:
      logged_bw = st.number_input(
          "Body Weight (kg)",
          min_value=30.0,
          max_value=250.0,
          value=float(st.session_state.user_profile.get("body_weight", 88.0)),
          step=0.1,
      )
    with c2:
      logged_weight_date = st.date_input(
          "Date", datetime.today(), key="bw_date"
      )

    bw_notes = st.text_input(
        "Notes (e.g., Morning weigh-in, post-run)",
        placeholder="Optional notes",
        key="bw_notes",
    )
    submit_bw = st.form_submit_button("Save Body Weight Entry")

    if submit_bw:
      try:
        if DB_MODE == "cloud":
          cursor = conn.cursor()
        else:
          local_conn = sqlite3.connect(DB_FILE)
          cursor = local_conn.cursor()

        cursor.execute(
            """
                    INSERT INTO body_weight (date, body_weight, notes)
                    VALUES (?, ?, ?)
                """,
            (logged_weight_date.strftime("%Y/%m/%d"), logged_bw, bw_notes),
        )
        if DB_MODE == "cloud":
          conn.commit()
        else:
          local_conn.commit()
          local_conn.close()

        st.success(
            f"Successfully recorded body weight: {logged_bw} kg saved to"
            " database!"
        )
      except Exception as e:
        st.error(f"Error saving body weight: {e}")

  st.markdown("---")
  st.subheader("📈 Body Weight Trend")
  try:
    if DB_MODE == "cloud":
      df_bw = pd.read_sql_query(
          "SELECT date AS Date, body_weight AS 'Body Weight (kg)', notes AS Notes"
          " FROM body_weight ORDER BY date ASC",
          conn,
      )
    else:
      conn_bw = sqlite3.connect(DB_FILE)
      df_bw = pd.read_sql_query(
          "SELECT date AS Date, body_weight AS 'Body Weight (kg)', notes AS Notes"
          " FROM body_weight ORDER BY date ASC",
          conn_bw,
      )
      conn_bw.close()

    if not df_bw.empty:
      st.dataframe(df_bw, use_container_width=True)
      chart_bw_data = df_bw[["Date", "Body Weight (kg)"]].dropna()
      if not chart_bw_data.empty:
        st.markdown("### Weight Progression Chart")
        st.line_chart(
            chart_bw_data.set_index("Date"), use_container_width=True
        )
    else:
      st.info("No body weight entries logged yet.")
  except Exception as e:
    st.info(f"Could not load body weight chart: {e}")

with tab3:
  st.subheader("📈 Training Analytics & Progress Charts")
  try:
    if DB_MODE == "cloud":
      df_analytics = pd.read_sql_query(
          "SELECT date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts ORDER BY id ASC",
          conn,
      )
    else:
      conn_an = sqlite3.connect(DB_FILE)
      df_analytics = pd.read_sql_query(
          "SELECT date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts ORDER BY id ASC",
          conn_an,
      )
      conn_an.close()

    if not df_analytics.empty and "Total Volume (kg)" in df_analytics.columns:
      df_analytics["Clean_Volume"] = (
          df_analytics["Total Volume (kg)"]
          .astype(str)
          .str.replace("kg", "", regex=False)
          .str.replace("HR: ", "", regex=False)
          .str.replace("bpm", "", regex=False)
      )
      df_analytics["Clean_Volume"] = pd.to_numeric(
          df_analytics["Clean_Volume"], errors="coerce"
      ).fillna(0)

      st.markdown("### Total Lift Volume / Activity Output Over Time")
      chart_data = df_analytics[["Date", "Clean_Volume"]].dropna()
      if not chart_data.empty:
        st.line_chart(chart_data.set_index("Date"), use_container_width=True)
      else:
        st.info("Log a few workouts to see your progression chart!")

      st.markdown("---")
      st.markdown("### Filter History by Routine / Focus")
      df_analytics["Routine / Focus"] = df_analytics[
          "Routine / Focus"
      ].fillna("Unassigned")
      unique_routines = sorted(df_analytics["Routine / Focus"].unique().tolist())
      selected_routine = st.selectbox(
          "Select Routine to Inspect", unique_routines, key="analytics_routine"
      )
      filtered_df = df_analytics[
          df_analytics["Routine / Focus"] == selected_routine
      ]
      st.dataframe(filtered_df, use_container_width=True)
    else:
      st.info("Add entries to generate performance charts.")
  except Exception as e:
    st.info(f"Error loading charts: {e}")

with tab4:
  st.subheader("📖 Fitness Glossary & Terminology Guide")
  st.markdown("""
    * **RPE (Rate of Perceived Exertion):** A scale from **1 to 10** used to measure how intense a set felt relative to failure.
      * *10:* Absolute maximum effort (0 reps left in the tank).
      * *8 - 9:* Hard set; you could have realistically done 1 or 2 more reps.
      * *6 - 7:* Moderate effort; comfortable with several reps left.
    * **Total Volume:** The overall workload calculated as Sets $\\times$ Reps $\\times$ Weight. Tracking volume over time is key for progressive overload and muscle hypertrophy.
    * **Cardio Pace:** Calculated as time divided by distance (Minutes / km) to track running/cardio efficiency over time.
    * **Home Workouts:** Bodyweight training focused on time-under-tension, high rep ranges, and calisthenics progression.
    * **Routine / Focus:** The structural split of your training day (e.g., Upper/Lower Body, Home Workouts, Cardio) ensuring balanced recovery and growth.
    """)

with tab5:
  st.subheader("💬 Tester Suggestion & Review Box")
  st.write(
      "Have a suggestion, found a bug, or want to leave feedback on the app?"
      " Drop it below!"
  )

  with st.form("feedback_form"):
    fb_name = st.text_input("Your Name / Handle", value=current_user)
    fb_rating = st.slider(
        "Rating (1 = Needs Work, 5 = Awesome!)",
        min_value=1,
        max_value=5,
        value=5,
    )
    fb_category = st.selectbox(
        "Feedback Category",
        [
            "General Review",
            "Bug Report",
            "Feature Request",
            "UI / Design Suggestion",
        ],
    )
    fb_message = st.text_area(
        "Your Feedback or Suggestion",
        placeholder="Type your feedback here...",
    )
    submit_fb = st.form_submit_button("Submit Feedback")

    if submit_fb:
      if fb_message.strip():
        try:
          if DB_MODE == "cloud":
            cursor = conn.cursor()
          else:
            local_conn = sqlite3.connect(DB_FILE)
            cursor = local_conn.cursor()

          now_dt = datetime.now()
          fb_date_str = now_dt.strftime("%Y/%m/%d")
          fb_time_str = now_dt.strftime("%H:%M:%S")

          cursor.execute(
              """
                    INSERT INTO reviews (date, time, tester_name, rating, category, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
              (
                  fb_date_str,
                  fb_time_str,
                  fb_name,
                  fb_rating,
                  fb_category,
                  fb_message,
              ),
          )
          if DB_MODE == "cloud":
            conn.commit()
          else:
            local_conn.commit()
            local_conn.close()

          st.success("Thank you! Your feedback has been successfully saved.")
        except Exception as e:
          st.error(f"Error saving feedback: {e}")
      else:
          st.warning("Please type a message before submitting.")

  st.markdown("---")
  st.subheader("📥 Received Feedback & Reviews")
  try:
    if DB_MODE == "cloud":
      df_fb = pd.read_sql_query(
          "SELECT date AS Date, time AS Time, tester_name AS 'Tester Name',"
          " rating AS 'Rating (1-5)', category AS Category, message AS 'Feedback"
          " Message' FROM reviews ORDER BY id DESC",
          conn,
      )
    else:
      conn_rev = sqlite3.connect(DB_FILE)
      df_fb = pd.read_sql_query(
          "SELECT date AS Date, time AS Time, tester_name AS 'Tester Name',"
          " rating AS 'Rating (1-5)', category AS Category, message AS 'Feedback"
          " Message' FROM reviews ORDER BY id DESC",
          conn_rev,
      )
      conn_rev.close()

    if not df_fb.empty:
      st.dataframe(df_fb, use_container_width=True)
    else:
      st.info("No reviews submitted yet.")
  except Exception as e:
    st.info(f"Could not load reviews: {e}")
