from datetime import datetime
import io
import os
import sqlite3
import pandas as pd
import streamlit as st

# --- DATABASE CONFIGURATION ---
try:
  import libsql

  db_url = st.secrets["TURSO_DATABASE_URL"]
  auth_token = st.secrets["TURSO_AUTH_TOKEN"]
  DB_MODE = "cloud"
except Exception:
  DB_FILE = "workout_master.db"
  DB_MODE = "local"


@st.cache_resource
def get_db_connection():
  """Returns a cached, thread-safe database connection for maximum speed."""
  if DB_MODE == "cloud":
    return libsql.connect(database=db_url, auth_token=auth_token)
  else:
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()

  # 1. Workouts Table with username isolation
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
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
  cursor.execute("PRAGMA table_info(workouts)")
  workout_cols = [col[1] for col in cursor.fetchall()]
  if "username" not in workout_cols:
    cursor.execute("ALTER TABLE workouts ADD COLUMN username TEXT")

  # 2. Cardio Table with username isolation
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS cardio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TEXT,
            activity TEXT,
            distance REAL,
            duration INTEGER,
            avg_hr INTEGER,
            pace TEXT
        )
    """)
  cursor.execute("PRAGMA table_info(cardio)")
  cardio_cols = [col[1] for col in cursor.fetchall()]
  if "username" not in cardio_cols:
    cursor.execute("ALTER TABLE cardio ADD COLUMN username TEXT")

  # 3. Reviews Table (Public submissions, admin view)
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

  # 4. Body Weight Table with username isolation
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS body_weight (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TEXT,
            body_weight REAL,
            notes TEXT
        )
    """)
  cursor.execute("PRAGMA table_info(body_weight)")
  bw_cols = [col[1] for col in cursor.fetchall()]
  if "username" not in bw_cols:
    cursor.execute("ALTER TABLE body_weight ADD COLUMN username TEXT")

  # 5. Profiles Table (Per-user settings with secure password protection & goals)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            password TEXT,
            body_weight REAL,
            gender TEXT,
            age INTEGER,
            height REAL,
            goal TEXT,
            target_bw REAL,
            target_bf REAL
        )
    """)
  cursor.execute("PRAGMA table_info(profiles)")
  profile_cols = [col[1] for col in cursor.fetchall()]
  if "password" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN password TEXT")
  if "goal" not in profile_cols:
    cursor.execute(
        "ALTER TABLE profiles ADD COLUMN goal TEXT DEFAULT 'Hourglass & Thick /"
        " Curvy Sculpting'"
    )
  if "target_bw" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN target_bw REAL DEFAULT 85.0")
  if "target_bf" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN target_bf REAL DEFAULT 22.0")

  cursor.execute("""
        INSERT OR IGNORE INTO profiles (username, password, body_weight, gender, age, height, goal, target_bw, target_bf)
        VALUES ('Modiri', '2026', 88.0, 'Male', 25, 178.0, 'Hourglass & Thick / Curvy Sculpting', 85.0, 22.0)
    """)

  conn.commit()


init_db()


# --- CACHED DATA FETCHERS FOR SPEED ---
@st.cache_data(ttl=300)
def fetch_workouts(username):
  conn = get_db_connection()
  return pd.read_sql_query(
      "SELECT id, date AS Date, routine AS 'Routine / Focus', exercise AS"
      " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
      " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
      " workouts WHERE username = ? ORDER BY id DESC",
      conn,
      params=(username,),
  )


@st.cache_data(ttl=300)
def fetch_cardio(username):
  conn = get_db_connection()
  return pd.read_sql_query(
      "SELECT id, date AS Date, activity AS Activity, distance AS"
      " 'Distance (km)', duration AS 'Duration (mins)', avg_hr AS 'Avg HR"
      " (bpm)', pace AS Pace FROM cardio WHERE username = ? ORDER BY id DESC",
      conn,
      params=(username,),
  )


@st.cache_data(ttl=300)
def fetch_body_weight(username):
  conn = get_db_connection()
  return pd.read_sql_query(
      "SELECT id, date AS Date, body_weight AS 'Body Weight (kg)', notes AS"
      " Notes FROM body_weight WHERE username = ? ORDER BY date ASC",
      conn,
      params=(username,),
  )


# --- ROUTINE EXERCISE MAPPINGS (THICK & CURVY / HOURGLASS FOCUS) ---
routine_exercises_map = {
    "Hourglass Lower Body A (Glute Max & Projection)": [
        "Heavy Barbell Hip Thrusts",
        "Romanian Deadlifts (RDLs) - Wide Stance",
        "Bulgarian Split Squats (Torso Leaned Forward)",
        "Seated Leg Press (High & Wide Foot Placement)",
        "Cable Pull-Throughs",
        "Standing Calf Raises",
    ],
    "Hourglass Lower Body B (Hip Width & Roundness)": [
        "Sumo Deadlifts or Sumo Squats",
        "Seated Machine Hip Abductors (Outer Glutes / Roundness)",
        "Cable Glute Kickbacks (Straight & Crossover)",
        "Smith Machine Curtsy Lunges",
        "Seated Hip Adductor Machine",
        "Dumbbell Walking Lunges",
    ],
    "Upper Body & Waist Definition (Hourglass Tone)": [
        "Lat Pulldown (Wide Grip for V-Taper)",
        "Incline Dumbbell Press",
        "Cable Face Pulls",
        "Dumbbell Lateral Raises",
        "Weighted Russian Twists",
        "Pallof Press (Core Stability & Waist Toning)",
    ],
    "Core & Waist-to-Hip Ratio": [
        "Hanging Knee / Leg Raises",
        "Cable Woodchoppers",
        "Plank with Hip Dips",
        "Decline Oblique Crunches",
        "Vacuum Holds (Transverse Abdominis Control)",
    ],
    "Strict Fat Loss Circuit": [
        "Stairmaster / Incline Treadmill (12-3-30)",
        "Kettlebell Sumo Deadlift High-Pulls",
        "Jump Squats / Bodyweight Plyometrics",
        "Mountain Climbers",
        "Assault Bike Intervals",
    ],
    "Cardio Equipment & Running": [
        "Treadmill Run / Jog",
        "Keiser Bicycle",
        "Arc Trainer",
        "Assault Bike",
        "Rowing Machine",
    ],
}


# --- HELPER FUNCTIONS ---
def reset_database():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("DROP TABLE IF EXISTS workouts")
  cursor.execute("DROP TABLE IF EXISTS cardio")
  cursor.execute("DROP TABLE IF EXISTS reviews")
  cursor.execute("DROP TABLE IF EXISTS body_weight")
  cursor.execute("DROP TABLE IF EXISTS profiles")
  conn.commit()
  st.cache_data.clear()
  init_db()


def delete_user_data(username_to_delete):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM workouts WHERE username = ?", (username_to_delete,))
  cursor.execute("DELETE FROM cardio WHERE username = ?", (username_to_delete,))
  cursor.execute(
      "DELETE FROM body_weight WHERE username = ?", (username_to_delete,)
  )
  cursor.execute("DELETE FROM profiles WHERE username = ?", (username_to_delete,))
  cursor.execute("DELETE FROM reviews WHERE tester_name = ?", (username_to_delete,))
  conn.commit()
  st.cache_data.clear()


def load_profile(username):
  conn = get_db_connection()
  try:
    df = pd.read_sql_query(
        "SELECT body_weight, gender, age, height, goal, target_bw, target_bf"
        " FROM profiles WHERE username = ?",
        conn,
        params=(username,),
    )
    if not df.empty:
      return {
          "body_weight": float(df["body_weight"].iloc[0]),
          "gender": df["gender"].iloc[0],
          "age": int(df["age"].iloc[0]),
          "height": float(df["height"].iloc[0]),
          "goal": (
              df["goal"].iloc[0]
              if pd.notna(df["goal"].iloc[0])
              else "Hourglass & Thick / Curvy Sculpting"
          ),
          "target_bw": (
              float(df["target_bw"].iloc[0])
              if pd.notna(df["target_bw"].iloc[0])
              else 85.0
          ),
          "target_bf": (
              float(df["target_bf"].iloc[0])
              if pd.notna(df["target_bf"].iloc[0])
              else 22.0
          ),
      }
  except Exception:
    pass
  return {
      "body_weight": 75.0,
      "gender": "Female",
      "age": 25,
      "height": 165.0,
      "goal": "Hourglass & Thick / Curvy Sculpting",
      "target_bw": 70.0,
      "target_bf": 20.0,
  }


def save_profile_db(username, profile_data):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        UPDATE profiles 
        SET body_weight = ?, gender = ?, age = ?, height = ?, goal = ?, target_bw = ?, target_bf = ?
        WHERE username = ?
    """,
      (
          profile_data["body_weight"],
          profile_data["gender"],
          profile_data["age"],
          profile_data["height"],
          profile_data["goal"],
          profile_data["target_bw"],
          profile_data["target_bf"],
          username,
      ),
  )
  conn.commit()
  st.cache_data.clear()


# --- SESSION STATE INITIALIZATION & PROFILE PRE-LOADING ---
if "username" not in st.session_state:
  st.session_state.username = None
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

if st.session_state.logged_in and st.session_state.username:
  if (
      "current_loaded_user" not in st.session_state
      or st.session_state.current_loaded_user != st.session_state.username
  ):
    p_data = load_profile(st.session_state.username)
    st.session_state.body_weight = p_data.get("body_weight", 75.0)
    st.session_state.gender = p_data.get("gender", "Female")
    st.session_state.age = p_data.get("age", 25)
    st.session_state.height = p_data.get("height", 165.0)
    st.session_state.goal = p_data.get(
        "goal", "Hourglass & Thick / Curvy Sculpting"
    )
    st.session_state.target_bw = p_data.get("target_bw", 70.0)
    st.session_state.target_bf = p_data.get("target_bf", 20.0)
    st.session_state.current_loaded_user = st.session_state.username
else:
  if "body_weight" not in st.session_state:
    st.session_state.body_weight = 75.0
  if "gender" not in st.session_state:
    st.session_state.gender = "Female"
  if "age" not in st.session_state:
    st.session_state.age = 25
  if "height" not in st.session_state:
    st.session_state.height = 165.0
  if "goal" not in st.session_state:
    st.session_state.goal = "Hourglass & Thick / Curvy Sculpting"
  if "target_bw" not in st.session_state:
    st.session_state.target_bw = 70.0
  if "target_bf" not in st.session_state:
    st.session_state.target_bf = 20.0

st.set_page_config(
    page_title="Workout Master Suite", page_icon="💪", layout="centered"
)

# --- SIDEBAR FOR UNIQUE USER LOGIN & NESTED NAVIGATION ---
with st.sidebar:
  st.markdown("### 🔐 Secure User Login / Register")

  if not st.session_state.logged_in:
    st.caption(
        "Please log in or register to access your personal training dashboard."
    )
    input_username = st.text_input("Username", key="username_input")
    input_password = st.text_input(
        "Password / PIN", type="password", key="password_input"
    )

    if st.button("Login / Register Account"):
      u_clean = input_username.strip()
      p_clean = input_password.strip()

      if not u_clean:
        st.warning("Please enter a valid username.")
      elif not p_clean:
        st.warning("Please enter a password.")
      else:
        try:
          conn = get_db_connection()
          cursor = conn.cursor()
          cursor.execute(
              "SELECT password FROM profiles WHERE username = ?", (u_clean,)
          )
          row = cursor.fetchone()

          if row:
            stored_password = row[0]
            if stored_password == p_clean:
              st.session_state.username = u_clean
              st.session_state.logged_in = True
              st.success(f"Welcome back, {u_clean}!")
              st.rerun()
            else:
              st.error(
                  "Incorrect password! This username is already taken by"
                  " someone else."
              )
          else:
            cursor.execute(
                """
                            INSERT INTO profiles (username, password, body_weight, gender, age, height, goal, target_bw, target_bf)
                            VALUES (?, ?, 75.0, 'Female', 25, 165.0, 'Hourglass & Thick / Curvy Sculpting', 70.0, 20.0)
                        """,
                (u_clean, p_clean),
            )
            conn.commit()
            st.cache_data.clear()

            st.session_state.username = u_clean
            st.session_state.logged_in = True
            st.success(f"New account created and logged in as {u_clean}!")
            st.rerun()
        except Exception as e:
          st.error(f"Authentication error: {e}")
  else:
    st.success(f"Logged in as: **{st.session_state.username}**")
    if st.button("Log Out"):
      st.session_state.logged_in = False
      st.session_state.username = None
      st.session_state.pop("current_loaded_user", None)
      st.rerun()

    st.markdown("---")
    st.markdown("### 🧭 Nested Navigation")

    main_category = st.selectbox(
        "Menu Category",
        [
            "📝 Logging & Workouts",
            "📈 Tracking & Analytics",
            "⚙️ System & Info",
        ],
    )

    if main_category == "📝 Logging & Workouts":
      selected_page = st.radio(
          "Select Sub-Page", ["📝 Logger Form", "🎯 Goals & Workout Plan"]
      )
    elif main_category == "📈 Tracking & Analytics":
      selected_page = st.radio(
          "Select Sub-Page",
          ["⚖️ Body Weight Tracker", "📈 Progress & Analytics"],
      )
    else:
      selected_page = st.radio(
          "Select Sub-Page", ["📖 Glossary & Feedback", "🔒 Admin Dashboard"]
      )

    st.markdown("---")
    st.markdown("### ⚙️ Athlete Profile")
    st.number_input(
        "Body Weight (kg)",
        min_value=30.0,
        max_value=250.0,
        step=0.5,
        key="body_weight",
    )
    st.selectbox("Gender", ["Female", "Male", "Other"], key="gender")
    st.number_input("Age", min_value=10, max_value=100, key="age")
    st.number_input(
        "Height (cm)", min_value=100.0, max_value=250.0, step=1.0, key="height"
    )

    if st.button("Save Profile"):
      updated_profile = {
          "body_weight": st.session_state.body_weight,
          "gender": st.session_state.gender,
          "age": st.session_state.age,
          "height": st.session_state.height,
          "goal": st.session_state.goal,
          "target_bw": st.session_state.target_bw,
          "target_bf": st.session_state.target_bf,
      }
      save_profile_db(st.session_state.username, updated_profile)
      st.success("Profile saved and synced securely!")

    st.markdown("---")
    st.markdown("### 💾 Personal Data Export")

    try:
      conn = get_db_connection()
      df_exp_workouts = pd.read_sql_query(
          "SELECT * FROM workouts WHERE username = ?",
          conn,
          params=(st.session_state.username,),
      )
      df_exp_cardio = pd.read_sql_query(
          "SELECT * FROM cardio WHERE username = ?",
          conn,
          params=(st.session_state.username,),
      )
      df_exp_bw = pd.read_sql_query(
          "SELECT * FROM body_weight WHERE username = ?",
          conn,
          params=(st.session_state.username,),
      )
      df_exp_profile = pd.read_sql_query(
          "SELECT username, body_weight, gender, age, height, goal, target_bw,"
          " target_bf FROM profiles WHERE username = ?",
          conn,
          params=(st.session_state.username,),
      )

      output = io.BytesIO()
      with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exp_workouts.to_excel(writer, sheet_name="Workout Log", index=False)
        df_exp_cardio.to_excel(writer, sheet_name="Cardio Log", index=False)
        df_exp_bw.to_excel(writer, sheet_name="Body Weight Log", index=False)
        df_exp_profile.to_excel(writer, sheet_name="Profile", index=False)
      excel_data = output.getvalue()

      st.download_button(
          label="📥 Download My Excel Backup",
          data=excel_data,
          file_name=(
              f"Workout_Master_{st.session_state.username}_Backup.xlsx"
          ),
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
      )
    except Exception as e:
      st.error(f"Could not prepare Excel download: {e}")

# --- AUTHENTICATION GATEKEEPER ---
if not st.session_state.logged_in:
  st.title("💪 Workout Master Suite")
  st.info(
      "👈 **Please log in or create an account using the sidebar to unlock your"
      " training suite.**"
  )
  st.stop()

current_user = st.session_state.username

st.title(f"💪 {current_user}'s Workout Master Suite")
st.write(
    f"Private elite training tracker for **{current_user}** (BW:"
    f" {st.session_state.body_weight}kg) with high-speed cloud sync."
)

# --- MAIN SCREEN DATA POLICY & PRIVACY ---
with st.expander("🛡️ Data Policy & Privacy Information", expanded=False):
  st.markdown("""
* **Private & Secure:** Your workout logs, body weight entries, and profile metrics are strictly isolated to your username and protected via secure authentication.
* **Cloud Sync:** Data is securely synced to cloud databases for reliable multi-device access.
* **Full Control:** You can export your raw data to Excel anytime or manage/wipe your account data securely via the admin tools.
""")

st.markdown("---")

if "selected_page" not in locals() and "selected_page" not in globals():
  selected_page = "📝 Logger Form"

# ==========================================
# PAGE 1: LOGGER FORM
# ==========================================
if selected_page == "📝 Logger Form":
  st.subheader("Add Workout or Cardio Activity")

  log_type = st.radio(
      "Select Activity Type to Log",
      ["🏋️ Strength & Bodyweight Workout", "🏃 Cardio Session"],
      horizontal=True,
  )

  if log_type == "🏋️ Strength & Bodyweight Workout":
    col1, col2 = st.columns(2)
    with col1:
      routine_options = list(routine_exercises_map.keys()) + ["Custom"]
      routine = st.selectbox("Routine / Focus", routine_options)

      if routine == "Custom":
        routine_name = st.text_input("Enter custom routine name", "Custom Focus")
        available_exercises = [
            "Heavy Barbell Hip Thrusts",
            "Romanian Deadlifts",
            "Lat Pulldown",
        ]
      else:
        routine_name = routine
        available_exercises = routine_exercises_map.get(routine, [])

    with col2:
      exercise_choice = st.selectbox(
          "Select Exercise", available_exercises + ["Other (Type Below)"]
      )
      if exercise_choice == "Other (Type Below)":
        exercise_name = st.text_input("Type Exercise Name", "New Exercise")
      else:
        exercise_name = exercise_choice

    st.markdown("---")
    st.write(
        "🏋️ **Set & Weight Progression (Pyramids / Hourglass Focus)**"
    )
    st.info(
        "💡 **Pro Tip:** For glute and lower body growth, focus on a 2-3 second"
        " eccentric (lowering) phase and a hard contraction at the top!"
    )

    num_blocks = st.selectbox(
        "How many different weight blocks?", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=0
    )

    total_sets = 0
    total_volume = 0
    weight_parts = []
    representative_reps = 10

    for i in range(num_blocks):
      if num_blocks > 1:
        st.caption(f"Block {i+1}")

      c1, c2, c3 = st.columns(3)
      with c1:
        s = st.number_input(
            f"Sets ({i+1})",
            min_value=1,
            max_value=20,
            value=3 if i > 0 else 4,
            key=f"sets_{i}",
        )
      with c2:
        r = st.number_input(
            f"Reps ({i+1})",
            min_value=1,
            max_value=100,
            value=12,
            key=f"reps_{i}",
        )
      with c3:
        w = st.number_input(
            f"Weight kg ({i+1}) (0 for Bodyweight)",
            min_value=0.0,
            max_value=500.0,
            value=0.0 if "Circuit" in routine else 30.0 + (i * 5.0),
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
      log_date = st.date_input("Workout Date", datetime.today(), key="lift_date")

    if st.button("Save Workout Entry"):
      try:
        conn = get_db_connection()
        cursor = conn.cursor()
        date_str = log_date.strftime("%Y/%m/%d")
        cursor.execute(
            """
                INSERT INTO workouts (username, date, routine, exercise, sets, reps, weight, total_volume, rpe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                st.session_state.username,
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
        conn.commit()
        st.cache_data.clear()

        st.success(
            f"Successfully logged {exercise_name} ({weight_str}) under"
            f" {routine_name} for {st.session_state.username}!"
        )
        st.rerun()
      except Exception as e:
        st.error(f"Error saving workout entry: {e}")

  else:  # Cardio Session
    st.write("🏃 **Cardio Metrics**")
    cardio_activity_options = [
        "Stairmaster / Incline Treadmill",
        "Outside Running",
        "Indoor Treadmill Run",
        "Keiser Bicycle",
        "Assault Bike",
        "Rowing Machine",
        "Other",
    ]
    cardio_act = st.selectbox("Cardio Activity", cardio_activity_options)
    if cardio_act == "Other":
      cardio_activity_name = st.text_input(
          "Type Cardio Activity", "Custom Cardio"
      )
    else:
      cardio_activity_name = cardio_act

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
          "Avg Heart Rate (bpm)", min_value=0, max_value=220, value=140, step=1
      )

    if cardio_dist > 0:
      pace_mins = int(cardio_time // cardio_dist)
      pace_secs = int(((cardio_time / cardio_dist) - pace_mins) * 60)
      pace_str = f"{pace_mins}m {pace_secs}s / km"
    else:
      pace_str = "N/A"

    st.info(
        f"📊 **Cardio Summary:** Activity: **{cardio_activity_name}** |"
        f" Distance: **{cardio_dist} km** | Duration: **{cardio_time} mins** |"
        f" Pace: **{pace_str}** | HR: **{cardio_hr if cardio_hr > 0 else 'N/A'}"
        " bpm**"
    )

    st.markdown("---")
    cardio_date = st.date_input(
        "Cardio Date", datetime.today(), key="cardio_date_input"
    )

    if st.button("Save Cardio Entry"):
      try:
        conn = get_db_connection()
        cursor = conn.cursor()
        date_str = cardio_date.strftime("%Y/%m/%d")
        cursor.execute(
            """
                INSERT INTO cardio (username, date, activity, distance, duration, avg_hr, pace)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                st.session_state.username,
                date_str,
                cardio_activity_name,
                float(cardio_dist),
                int(cardio_time),
                int(cardio_hr),
                pace_str,
            ),
        )
        conn.commit()
        st.cache_data.clear()

        st.success(
            f"Successfully logged {cardio_activity_name} for"
            f" {st.session_state.username}!"
        )
        st.rerun()
      except Exception as e:
        st.error(f"Error saving cardio entry: {e}")

  st.markdown("---")
  st.subheader(f"📊 My Live Logs ({st.session_state.username})")

  sub_tab_prev1, sub_tab_prev2 = st.tabs(
      ["🏋️ Strength Workouts Log", "🏃 Cardio Sessions Log"]
  )

  with sub_tab_prev1:
    df_log = fetch_workouts(st.session_state.username)
    if not df_log.empty:
      st.dataframe(df_log.drop(columns=["id"]).head(50), use_container_width=True)

      with st.expander("🗑️ Manage & Delete Workout Entries", expanded=False):
        st.write("Select specific workout entry IDs to delete.")
        workout_options = dict(
            zip(
                df_log["id"],
                df_log["Date"]
                + " | "
                + df_log["Routine / Focus"]
                + " | "
                + df_log["Exercise"]
                + " ("
                + df_log["Weight (kg)"]
                + ")",
            )
        )
        selected_to_delete = st.multiselect(
            "Choose workout entries to remove",
            options=list(workout_options.keys()),
            format_func=lambda x: workout_options[x],
            key="del_workouts_multi",
        )

        if st.button("Delete Selected Workout Entries", type="primary"):
          if selected_to_delete:
            try:
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.executemany(
                  "DELETE FROM workouts WHERE id = ? AND username = ?",
                  [
                      (wid, st.session_state.username)
                      for wid in selected_to_delete
                  ],
              )
              conn.commit()
              st.cache_data.clear()

              st.success(
                  f"Successfully deleted {len(selected_to_delete)} workout"
                  " entry/entries!"
              )
              st.rerun()
            except Exception as e:
              st.error(f"Error deleting entries: {e}")
          else:
            st.warning("Please select at least one entry to delete.")
    else:
      st.info(
          f"No strength workout entries logged for {st.session_state.username}"
          " yet."
      )

  with sub_tab_prev2:
    df_cardio_log = fetch_cardio(st.session_state.username)
    if not df_cardio_log.empty:
      st.dataframe(
          df_cardio_log.drop(columns=["id"]).head(50), use_container_width=True
      )

      with st.expander("🗑️ Manage & Delete Cardio Entries", expanded=False):
        st.write("Select specific cardio entry IDs to delete.")
        cardio_options = dict(
            zip(
                df_cardio_log["id"],
                df_cardio_log["Date"]
                + " | "
                + df_cardio_log["Activity"]
                + " ("
                + df_cardio_log["Distance (km)"].astype(str)
                + "km, "
                + df_cardio_log["Duration (mins)"].astype(str)
                + "m)",
            )
        )
        selected_cardio_to_delete = st.multiselect(
            "Choose cardio entries to remove",
            options=list(cardio_options.keys()),
            format_func=lambda x: cardio_options[x],
            key="del_cardio_multi",
        )

        if st.button("Delete Selected Cardio Entries", type="primary"):
          if selected_cardio_to_delete:
            try:
              conn = get_db_connection()
              cursor = conn.cursor()
              cursor.executemany(
                  "DELETE FROM cardio WHERE id = ? AND username = ?",
                  [
                      (cid, st.session_state.username)
                      for cid in selected_cardio_to_delete
                  ],
              )
              conn.commit()
              st.cache_data.clear()

              st.success(
                  f"Successfully deleted {len(selected_cardio_to_delete)}"
                  " cardio entry/entries!"
              )
              st.rerun()
            except Exception as e:
              st.error(f"Error deleting cardio entries: {e}")
          else:
            st.warning("Please select at least one entry to delete.")
    else:
      st.info(f"No cardio entries logged for {st.session_state.username} yet.")


# ==========================================
# PAGE 2: GOALS & WORKOUT PLAN
# ==========================================
elif selected_page == "🎯 Goals & Workout Plan":
  st.subheader("🎯 Goals & Detailed Plan Logger")
  st.write(
      "Define your primary fitness objective, configure your custom training"
      " days, and log completed sessions with precise metrics."
  )

  goal_options = [
      "Hourglass & Thick / Curvy Sculpting",
      "Strict Fat Loss",
      "Body Recomposition (Fat Loss & Muscle Gain)",
      "Hypertrophy / Muscle Building",
      "Cardiovascular Endurance & Running",
  ]

  current_goal_idx = (
      goal_options.index(st.session_state.goal)
      if st.session_state.goal in goal_options
      else 0
  )

  selected_goal = st.selectbox(
      "What is your primary fitness goal?", goal_options, index=current_goal_idx
  )

  c_g1, c_g2 = st.columns(2)
  with c_g1:
    target_bw_input = st.number_input(
        "Target Body Weight (kg)",
        min_value=40.0,
        max_value=200.0,
        value=float(st.session_state.target_bw),
        step=0.5,
    )
  with c_g2:
    target_bf_input = st.number_input(
        "Target Body Fat Percentage (%)",
        min_value=5.0,
        max_value=50.0,
        value=float(st.session_state.target_bf),
        step=0.5,
    )

  if st.button("Save Goal & Plan Settings"):
    st.session_state.goal = selected_goal
    st.session_state.target_bw = target_bw_input
    st.session_state.target_bf = target_bf_input

    updated_profile = {
        "body_weight": st.session_state.body_weight,
        "gender": st.session_state.gender,
        "age": st.session_state.age,
        "height": st.session_state.height,
        "goal": st.session_state.goal,
        "target_bw": st.session_state.target_bw,
        "target_bf": st.session_state.target_bf,
    }
    save_profile_db(st.session_state.username, updated_profile)
    st.success("Your goal and targets have been successfully saved!")

  st.markdown("---")
  st.markdown(f"### 📅 Custom Training Days & Schedule")
  st.write(
      "Select which days of the week you want to train and assign your daily"
      " focus."
  )

  all_days = [
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
      "Sunday",
  ]
  default_days = ["Monday", "Tuesday", "Thursday", "Friday", "Saturday"]

  chosen_training_days = st.multiselect(
      "Select the days of the week you want to train:",
      all_days,
      default=default_days,
      key="chosen_training_days_multiselect",
  )

  possible_focuses = [
      "Hourglass Lower Body A (Glute Max & Projection)",
      "Hourglass Lower Body B (Hip Width & Roundness)",
      "Upper Body & Waist Definition (Hourglass Tone)",
      "Core & Waist-to-Hip Ratio",
      "Strict Fat Loss Circuit",
      "Cardio Equipment & Running",
  ]

  plan_sessions = []
  if chosen_training_days:
    st.markdown("##### ⚙️ Assign Focus per Day:")
    for day in chosen_training_days:
      c_d1, c_d2 = st.columns([1, 2])
      with c_d1:
        st.markdown(f"**{day}**")
      with c_d2:
        default_idx = (
            0
            if "Monday" in day
            else (
                1
                if "Tuesday" in day
                else (
                    2
                    if "Thursday" in day
                    else (3 if "Friday" in day else 4)
                )
            )
        )
        if default_idx >= len(possible_focuses):
          default_idx = 0
        focus = st.selectbox(
            f"Focus for {day}",
            possible_focuses,
            index=default_idx,
            key=f"focus_{day}",
        )
        plan_sessions.append(f"{day}: {focus}")
  else:
    st.warning("Please select at least one training day of the week.")

  st.markdown("---")
  st.subheader(
      "🚀 Log Plan Session with Detailed Metrics (Weights, Sets, RPE, Reps &"
      " Distance)"
  )
  st.write(
      "Select a session from your customized schedule below and input your"
      " actual performance metrics to log it directly into your progress"
      " tracker."
  )

  if plan_sessions:
    chosen_session = st.selectbox(
        "Select Planned Session to Log",
        plan_sessions,
        key="plan_chosen_session",
    )
    plan_log_date = st.date_input(
        "Workout Date", datetime.today(), key="plan_log_date_picker"
    )

    is_cardio_session = (
        "Running" in chosen_session
        or "Run" in chosen_session
        or "Cardio" in chosen_session
        or "Circuit" in chosen_session
    )

    if is_cardio_session:
      st.markdown("##### 🏃 Cardio & Conditioning Metrics")
      c_dist = st.number_input(
          "Distance (km) / Intensity Equivalent",
          min_value=0.1,
          max_value=50.0,
          value=5.0,
          step=0.1,
      )
      c_dur = st.number_input(
          "Duration (mins)", min_value=1, max_value=300, value=30, step=1
      )
      c_hr = st.number_input(
          "Avg Heart Rate (bpm)", min_value=0, max_value=220, value=140
      )
    else:
      st.markdown(
          "##### 🏋️ Strength Metrics & Multi-Block Weight Progression"
      )
      num_blocks_plan = st.selectbox(
          "How many different weight blocks?",
          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          index=0,
          key="plan_num_blocks",
      )

      total_sets_p = 0
      total_volume_p = 0
      weight_parts_p = []
      representative_reps_p = 10

      for i in range(num_blocks_plan):
        if num_blocks_plan > 1:
          st.caption(f"Block {i+1}")

        c1, c2, c3 = st.columns(3)
        with c1:
          s_p = st.number_input(
              f"Sets ({i+1})",
              min_value=1,
              max_value=20,
              value=3 if i > 0 else 4,
              key=f"plan_sets_{i}",
          )
        with c2:
          r_p = st.number_input(
              f"Reps ({i+1})",
              min_value=1,
              max_value=100,
              value=12,
              key=f"plan_reps_{i}",
          )
        with c3:
          w_p = st.number_input(
              f"Weight kg ({i+1}) (0 for Bodyweight)",
              min_value=0.0,
              max_value=500.0,
              value=30.0 + (i * 5.0),
              step=2.5,
              key=f"plan_weight_{i}",
          )

        total_sets_p += s_p
        if i == 0:
          representative_reps_p = r_p

        total_volume_p += s_p * r_p * w_p
        weight_parts_p.append(f"{w_p}kg")

      if len(weight_parts_p) == 1:
        weight_str_p = weight_parts_p[0]
      elif len(weight_parts_p) == 2:
        weight_str_p = f"{weight_parts_p[0]} & {weight_parts_p[1]}"
      else:
        weight_str_p = (
            ", ".join(weight_parts_p[:-1]) + f" & {weight_parts_p[-1]}"
        )

      total_volume_str_p = f"{total_volume_p}kg"

      st.info(
          f"📊 **Calculated Summary:** Total Sets: **{total_sets_p}** | Combined"
          f" Weight: **{weight_str_p}** | Total Volume: **{total_volume_p} kg**"
      )

      p_rpe = st.slider(
          "RPE (Rate of Perceived Exertion 1-10)",
          min_value=1.0,
          max_value=10.0,
          value=8.0,
          step=0.5,
          key="plan_rpe_slider",
      )

    if st.button(
        "💾 Save Detailed Session to Progress Tracker", key="save_plan_btn"
    ):
      try:
        conn = get_db_connection()
        cursor = conn.cursor()
        date_str = plan_log_date.strftime("%Y/%m/%d")

        if is_cardio_session:
          if c_dist > 0:
            p_mins = int(c_dur // c_dist)
            p_secs = int(((c_dur / c_dist) - p_mins) * 60)
            pace_str = f"{p_mins}m {p_secs}s / km"
          else:
            pace_str = "N/A"

          cursor.execute(
              """
                  INSERT INTO cardio (username, date, activity, distance, duration, avg_hr, pace)
                  VALUES (?, ?, ?, ?, ?, ?, ?)
              """,
              (
                  st.session_state.username,
                  date_str,
                  chosen_session,
                  float(c_dist),
                  int(c_dur),
                  int(c_hr),
                  pace_str,
              ),
          )
          st.success(
              f"Successfully logged session '{chosen_session}' to your"
              " progress tracker!"
          )
        else:
          cursor.execute(
              """
                  INSERT INTO workouts (username, date, routine, exercise, sets, reps, weight, total_volume, rpe)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
              """,
              (
                  st.session_state.username,
                  date_str,
                  selected_goal,
                  chosen_session,
                  int(total_sets_p),
                  int(representative_reps_p),
                  weight_str_p,
                  total_volume_str_p,
                  float(p_rpe),
              ),
          )
          st.success(
              f"Successfully logged strength session '{chosen_session}'"
              f" ({total_sets_p} sets, {weight_str_p}, RPE {p_rpe}) to your"
              " progress tracker!"
          )

        conn.commit()
        st.cache_data.clear()
        st.rerun()
      except Exception as e:
        st.error(f"Error logging session: {e}")
  else:
    st.info("Please select at least one training day above to log sessions.")


# ==========================================
# PAGE 3: BODY WEIGHT TRACKER
# ==========================================
elif selected_page == "⚖️ Body Weight Tracker":
  st.subheader(f"⚖️ Body Weight Tracker ({st.session_state.username})")
  st.write("Log your body weight regularly to track progress toward your goals.")

  with st.form("body_weight_form"):
    c1, c2 = st.columns(2)
    with c1:
      logged_bw = st.number_input(
          "Body Weight (kg)",
          min_value=30.0,
          max_value=250.0,
          value=float(st.session_state.body_weight),
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
                    INSERT INTO body_weight (username, date, body_weight, notes)
                    VALUES (?, ?, ?, ?)
                """,
            (
                st.session_state.username,
                logged_weight_date.strftime("%Y/%m/%d"),
                logged_bw,
                bw_notes,
            ),
        )
        conn.commit()
        st.cache_data.clear()

        st.success(
            f"Successfully recorded body weight: {logged_bw} kg saved for"
            f" {st.session_state.username}!"
        )
      except Exception as e:
        st.error(f"Error saving body weight: {e}")

  st.markdown("---")
  st.subheader("📈 Body Weight Trend & Management")
  df_bw = fetch_body_weight(st.session_state.username)
  if not df_bw.empty:
    st.dataframe(df_bw.drop(columns=["id"]), use_container_width=True)
    chart_bw_data = df_bw[["Date", "Body Weight (kg)"]].dropna()
    if not chart_bw_data.empty:
      st.markdown("### Weight Progression Chart")
      st.line_chart(chart_bw_data.set_index("Date"), use_container_width=True)

    with st.expander("🗑️ Manage & Delete Body Weight Entries", expanded=False):
      st.write("Select specific body weight entry IDs to delete.")
      bw_options = dict(
          zip(
              df_bw["id"],
              df_bw["Date"]
              + " - "
              + df_bw["Body Weight (kg)"].astype(str)
              + "kg ("
              + df_bw["Notes"].fillna("No notes")
              + ")",
          )
      )
      selected_bw_to_delete = st.multiselect(
          "Choose body weight entries to remove",
          options=list(bw_options.keys()),
          format_func=lambda x: bw_options[x],
          key="del_bw_multiselect",
      )

      if st.button(
          "Delete Selected Body Weight Entries", type="primary", key="btn_del_bw"
      ):
        if selected_bw_to_delete:
          try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.executemany(
                "DELETE FROM body_weight WHERE id = ? AND username = ?",
                [
                    (wid, st.session_state.username)
                    for wid in selected_bw_to_delete
                ],
            )
            conn.commit()
            st.cache_data.clear()

            st.success(
                f"Successfully deleted {len(selected_bw_to_delete)} body weight"
                " entry/entries!"
            )
            st.rerun()
          except Exception as e:
            st.error(f"Error deleting body weight entries: {e}")
        else:
          st.warning("Please select at least one entry to delete.")
  else:
    st.info(f"No body weight entries logged for {st.session_state.username} yet.")


# ==========================================
# PAGE 4: PROGRESS & ANALYTICS
# ==========================================
elif selected_page == "📈 Progress & Analytics":
  st.subheader(f"📈 Training Analytics ({st.session_state.username})")

  an_tab1, an_tab2 = st.tabs(
      ["🏋️ Strength Analytics", "🏃 Cardio Performance Analytics"]
  )

  with an_tab1:
    df_analytics = fetch_workouts(st.session_state.username)
    if not df_analytics.empty and "Total Volume (kg)" in df_analytics.columns:
      df_analytics["Clean_Volume"] = (
          df_analytics["Total Volume (kg)"]
          .astype(str)
          .str.replace("kg", "", regex=False)
      )
      df_analytics["Clean_Volume"] = pd.to_numeric(
          df_analytics["Clean_Volume"], errors="coerce"
      ).fillna(0)

      st.markdown("### Total Lift Volume Over Time")
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
      st.dataframe(filtered_df.head(100), use_container_width=True)
    else:
      st.info("Add strength workout entries to generate performance charts.")

  with an_tab2:
    df_cardio_an = fetch_cardio(st.session_state.username)
    if not df_cardio_an.empty:
      st.markdown("### Cardio Distance Over Time")
      cardio_chart_data = df_cardio_an[["Date", "Distance (km)"]].dropna()
      if not cardio_chart_data.empty:
        st.line_chart(
            cardio_chart_data.set_index("Date"), use_container_width=True
        )

      st.markdown("---")
      st.markdown("### Cardio Logs History")
      st.dataframe(df_cardio_an.head(100), use_container_width=True)
    else:
      st.info("Log cardio sessions to view performance analytics!")


# ==========================================
# PAGE 5: GLOSSARY & FEEDBACK
# ==========================================
elif selected_page == "📖 Glossary & Feedback":
  st.subheader("📖 Glossary & Definitions")
  st.markdown("""
  * **Glute Max Projection:** Building thickness and rear lift through deep hip-extension movements like barbell hip thrusts and heavy RDLs.
  * **Hip Width & Roundness:** Targeting the gluteus medius and outer sweep using machine abductors and cable kickbacks to enhance the hourglass silhouette.
  * **Waist-to-Hip Ratio:** Balancing heavy lower body work with upper body lat development (V-taper illusion) and deep transverse abdominis core stability.
  * **RPE (Rate of Perceived Exertion):** A scale from 1 to 10 measuring training intensity. 10 is failure; 8 leaves 2 reps in reserve.
  """)

  st.markdown("---")
  st.subheader("💬 Feedback & Reviews")
  st.write(
      "Share your thoughts, feature requests, or bug reports regarding the"
      " Workout Master Suite."
  )

  with st.form("review_form"):
    tester_name = st.text_input(
        "Your Name / Handle", value=st.session_state.username
    )
    rating = st.slider("Rating", min_value=1, max_value=5, value=5)
    category = st.selectbox(
        "Category",
        [
            "Feature Request",
            "Bug Report",
            "UI/UX Feedback",
            "General Praise",
        ],
    )
    message = st.text_area(
        "Message / Feedback", placeholder="Type your feedback here..."
    )
    submit_review = st.form_submit_button("Submit Review")

    if submit_review:
      try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_date = datetime.today().strftime("%Y/%m/%d")
        current_time_str = datetime.now().strftime("%H:%M:%S")
        cursor.execute(
            """
                INSERT INTO reviews (date, time, tester_name, rating, category, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                current_date,
                current_time_str,
                tester_name,
                rating,
                category,
                message,
            ),
        )
        conn.commit()
        st.cache_data.clear()

        st.success("Thank you! Your feedback has been successfully submitted.")
      except Exception as e:
        st.error(f"Error submitting review: {e}")


# ==========================================
# PAGE 6: ADMIN DASHBOARD
# ==========================================
elif selected_page == "🔒 Admin Dashboard":
  st.subheader("🔒 Admin Dashboard (Maker Only)")
  st.write(
      "Enter the Admin PIN to view incoming user reviews and manage accounts."
  )

  admin_pin = st.text_input("Admin PIN", type="password", key="admin_pin_input")

  if admin_pin == "2026":
    st.success("Admin access granted!")

    st.markdown("---")
    st.markdown("### 👤 Particular User Account Reset & Deletion")
    st.write(
        "Select a specific user account to wipe their profile, password, and all"
        " workouts, cardio, and body weight logs."
    )

    try:
      conn = get_db_connection()
      df_users = pd.read_sql_query("SELECT username FROM profiles", conn)

      if not df_users.empty:
        user_list = df_users["username"].tolist()
        selected_user_to_reset = st.selectbox(
            "Select User Account", user_list, key="select_user_to_reset"
        )

        col_u1, col_u2 = st.columns([2, 1])
        with col_u1:
          st.warning(
              f"This will permanently delete user **{selected_user_to_reset}**"
              " and all their associated data."
          )
        with col_u2:
          if st.button(
              f"🗑️ Delete User '{selected_user_to_reset}'",
              type="primary",
              key="btn_del_specific_user",
          ):
            delete_user_data(selected_user_to_reset)
            if st.session_state.username == selected_user_to_reset:
              st.session_state.logged_in = False
              st.session_state.username = None
              st.session_state.pop("current_loaded_user", None)
            st.success(
                f"Successfully deleted user '{selected_user_to_reset}' and all"
                " associated data!"
            )
            st.rerun()
      else:
        st.info("No registered user accounts found.")
    except Exception as e:
      st.error(f"Error loading user accounts: {e}")

    st.markdown("---")
    with st.expander("⚠️ Danger Zone: Global Database Reset", expanded=False):
      st.warning(
          "Clicking this button will permanently delete ALL user accounts and"
          " data across the entire app, reverting to the default `Modiri`"
          " account."
      )
      if st.button(
          "🗑️ Wipe & Reset Entire Database Now",
          type="primary",
          key="btn_reset_db",
      ):
        reset_database()
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.pop("current_loaded_user", None)
        st.success(
            "Database has been completely wiped and reset for everyone!"
        )
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Submitted Reviews History")
    try:
      conn = get_db_connection()
      df_reviews = pd.read_sql_query(
          "SELECT date AS Date, time AS Time, tester_name AS 'Tester', rating AS"
          " 'Rating (1-5)', category AS Category, message AS Message FROM"
          " reviews ORDER BY id DESC",
          conn,
      )

      if not df_reviews.empty:
        st.dataframe(df_reviews.head(50), use_container_width=True)
      else:
        st.info("No reviews submitted yet.")
    except Exception as e:
      st.info(f"Could not load reviews: {e}")
  elif admin_pin != "":
    st.error("Incorrect Admin PIN.")
  else:
    st.info("Please enter your Admin PIN to unlock the admin dashboard.")
