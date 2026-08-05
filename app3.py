from datetime import datetime
import io
import os
import sqlite3
import pandas as pd
import streamlit as st

# --- APP VERSION & CHANGELOG CONFIGURATION ---
CURRENT_VERSION = "v1.3.3"
CHANGELOG = {
    "v1.3.3": [
        (
            "👥 Added a **Registered User Profiles** tracking table back to the"
            " Admin Dashboard."
        ),
        (
            "✏️ Full **Edit & Update** support maintained for both strength"
            " workouts and cardio sessions."
        ),
        (
            "⚡ Retained `st.fragment` isolation on the logger form for smooth"
            " interaction."
        ),
    ],
    "v1.3.2": [
        (
            "✏️ Added full **Edit & Update** support for both strength"
            " workouts and cardio sessions."
        ),
        (
            "⚡ Implemented `st.fragment` isolation on the logger form to"
            " eliminate full-page dimming when changing weights, sets, or"
            " routines."
        ),
        (
            "✨ Added automated 'What's New' changelog notification system for"
            " every update."
        ),
    ],
    "v1.3.1": [
        (
            "🔐 Enhanced multi-user secure authentication and cloud database"
            " synchronization."
        ),
        "📊 Added direct Excel backup export for raw training data.",
    ],
}

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
            target_bf REAL,
            last_seen_version TEXT
        )
    """)
  cursor.execute("PRAGMA table_info(profiles)")
  profile_cols = [col[1] for col in cursor.fetchall()]
  if "password" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN password TEXT")
  if "goal" not in profile_cols:
    cursor.execute(
        "ALTER TABLE profiles ADD COLUMN goal TEXT DEFAULT 'Body Recomposition'"
    )
  if "target_bw" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN target_bw REAL DEFAULT 85.0")
  if "target_bf" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN target_bf REAL DEFAULT 22.0")
  if "last_seen_version" not in profile_cols:
    cursor.execute(
        "ALTER TABLE profiles ADD COLUMN last_seen_version TEXT DEFAULT 'v1.0.0'"
    )

  cursor.execute("""
        INSERT OR IGNORE INTO profiles (username, password, body_weight, gender, age, height, goal, target_bw, target_bf, last_seen_version)
        VALUES ('Modiri', '2026', 88.0, 'Male', 25, 178.0, 'Body Recomposition (Fat Loss & Muscle Gain)', 85.0, 22.0, 'v1.0.0')
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


def load_profile(username):
  conn = get_db_connection()
  try:
    df = pd.read_sql_query(
        "SELECT body_weight, gender, age, height, goal, target_bw, target_bf,"
        " last_seen_version FROM profiles WHERE username = ?",
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
              else "Body Recomposition"
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
          "last_seen_version": (
              df["last_seen_version"].iloc[0]
              if pd.notna(df["last_seen_version"].iloc[0])
              else "v1.0.0"
          ),
      }
  except Exception:
    pass
  return {
      "body_weight": 75.0,
      "gender": "Male",
      "age": 25,
      "height": 175.0,
      "goal": "Body Recomposition (Fat Loss & Muscle Gain)",
      "target_bw": 85.0,
      "target_bf": 22.0,
      "last_seen_version": "v1.0.0",
  }


def save_profile_db(username, profile_data):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        UPDATE profiles 
        SET body_weight = ?, gender = ?, age = ?, height = ?, goal = ?, target_bw = ?, target_bf = ?, last_seen_version = ?
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
          profile_data["last_seen_version"],
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
if "whats_new_shown" not in st.session_state:
  st.session_state.whats_new_shown = False

if st.session_state.logged_in and st.session_state.username:
  if (
      "current_loaded_user" not in st.session_state
      or st.session_state.current_loaded_user != st.session_state.username
  ):
    p_data = load_profile(st.session_state.username)
    st.session_state.body_weight = p_data.get("body_weight", 75.0)
    st.session_state.gender = p_data.get("gender", "Male")
    st.session_state.age = p_data.get("age", 25)
    st.session_state.height = p_data.get("height", 175.0)
    st.session_state.goal = p_data.get(
        "goal", "Body Recomposition (Fat Loss & Muscle Gain)"
    )
    st.session_state.target_bw = p_data.get("target_bw", 85.0)
    st.session_state.target_bf = p_data.get("target_bf", 22.0)
    st.session_state.last_seen_version = p_data.get(
        "last_seen_version", "v1.0.0"
    )
    st.session_state.current_loaded_user = st.session_state.username
else:
  if "body_weight" not in st.session_state:
    st.session_state.body_weight = 75.0
  if "gender" not in st.session_state:
    st.session_state.gender = "Male"
  if "age" not in st.session_state:
    st.session_state.age = 25
  if "height" not in st.session_state:
    st.session_state.height = 175.0
  if "goal" not in st.session_state:
    st.session_state.goal = "Body Recomposition (Fat Loss & Muscle Gain)"
  if "target_bw" not in st.session_state:
    st.session_state.target_bw = 85.0
  if "target_bf" not in st.session_state:
    st.session_state.target_bf = 22.0
  if "last_seen_version" not in st.session_state:
    st.session_state.last_seen_version = "v1.0.0"

st.set_page_config(
    page_title="Workout Master Suite", page_icon="💪", layout="centered"
)


# --- WHAT'S NEW MODAL DIALOG ---
@st.dialog(f"📢 What's New in {CURRENT_VERSION}!")
def show_whats_new_dialog():
  st.write(
      f"We just pushed a new update! Here is what changed in"
      f" **{CURRENT_VERSION}**:"
  )
  for bullet in CHANGELOG.get(CURRENT_VERSION, ["General performance updates."]):
    st.markdown(f"- {bullet}")

  st.markdown("---")
  if st.button("Got it! Let's Train 🚀", type="primary"):
    st.session_state.last_seen_version = CURRENT_VERSION
    if st.session_state.logged_in and st.session_state.username:
      p_data = load_profile(st.session_state.username)
      p_data["last_seen_version"] = CURRENT_VERSION
      save_profile_db(st.session_state.username, p_data)
    st.rerun()


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
              st.session_state.whats_new_shown = False
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
                            INSERT INTO profiles (username, password, body_weight, gender, age, height, goal, target_bw, target_bf, last_seen_version)
                            VALUES (?, ?, 75.0, 'Male', 25, 175.0, 'Body Recomposition (Fat Loss & Muscle Gain)', 85.0, 22.0, 'v1.0.0')
                        """,
                (u_clean, p_clean),
            )
            conn.commit()
            st.cache_data.clear()

            st.session_state.username = u_clean
            st.session_state.logged_in = True
            st.session_state.whats_new_shown = False
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
      st.session_state.whats_new_shown = False
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
          "Select Sub-Page",
          ["📖 Glossary & Feedback", "🔒 Admin Dashboard", "📢 What's New Log"],
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
    st.selectbox("Gender", ["Male", "Female", "Other"], key="gender")
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
          "last_seen_version": st.session_state.last_seen_version,
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

# --- TRIGGER WHAT'S NEW DIALOG ON LOGIN (ONLY ONCE PER SESSION) ---
if (
    not st.session_state.whats_new_shown
    and st.session_state.last_seen_version != CURRENT_VERSION
):
  show_whats_new_dialog()
  st.session_state.whats_new_shown = True

st.title(f"💪 {current_user}'s Workout Master Suite")
st.write(
    f"Private elite training tracker for **{current_user}** (BW:"
    f" {st.session_state.body_weight}kg) | Version: **{CURRENT_VERSION}**"
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
# PAGE 1: LOGGER FORM (ISOLATED VIA ST.FRAGMENT)
# ==========================================
if selected_page == "📝 Logger Form":
  st.subheader("Add Workout or Cardio Activity")

  @st.fragment
  def render_logger_fragment():
    log_type = st.radio(
        "Select Activity Type to Log",
        ["🏋️ Strength & Bodyweight Workout", "🏃 Cardio Session"],
        key="log_type_selector",
        horizontal=True,
    )

    if log_type == "🏋️ Strength & Bodyweight Workout":
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
              "Seated Leg Press",
              "Leg Extensions",
              "Machine Leg Curl",
              "Romanian Deadlift",
              "Standing Calf Raises",
              "Seated Calf Raises",
          ],
          "Lower Body B": [
              "Bulgarian Split Squat",
              "Goblet Squat",
              "Seated Leg Press",
              "Leg Extensions",
              "Machine Leg Curl",
              "Romanian Deadlift",
              "Standing Calf Raises",
          ],
          "Core & Abs": [
              "Abdominal Crunch Machines",
              "Cable Crunches",
              "Hanging Leg Raises",
              "Plank Hold",
              "Russian Twists",
              "Decline Sit-Ups",
          ],
          "Cardio Equipment": [
              "Keiser Bicycle",
              "Arc Trainer",
              "Treadmill Run",
              "Assault Bike",
              "Rowing Machine",
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
          "Full Body": [
              "Barbell Back Squat",
              "Barbell Bench Press",
              "Lat Pulldown",
              "Seated Leg Press",
              "Leg Extensions",
              "Standing Calf Raises",
          ],
      }

      col1, col2 = st.columns(2)
      with col1:
        routine_options = list(routine_exercises_map.keys()) + ["Custom"]
        routine = st.selectbox(
            "Routine / Focus", routine_options, key="routine_sel"
        )

        if routine == "Custom":
          routine_name = st.text_input(
              "Enter custom routine name",
              "Custom Focus",
              key="custom_routine_name",
          )
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
            "Select Exercise",
            available_exercises + ["Other (Type Below)"],
            key="ex_sel",
        )
        if exercise_choice == "Other (Type Below)":
          exercise_name = st.text_input(
              "Type Exercise Name", "New Exercise", key="custom_ex_name"
          )
        else:
          exercise_name = exercise_choice

      st.markdown("---")
      st.write("🏋️ **Set & Weight Progression (Pyramids / Weight Changes)**")
      st.info(
          "💡 **Pro Tip:** Remember to take at least **2 minutes of rest**"
          " between working sets for optimal ATP recovery and muscle growth!"
      )

      num_blocks = st.selectbox(
          "How many different weight blocks?",
          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          index=0,
          key="num_blocks_sel",
      )

      with st.form("workout_form"):
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
            f"📊 **Calculated Summary:** Total Sets: **{total_sets}** |"
            f" Combined Weight: **{weight_str}** | Total Volume: **{total_volume}"
            " kg**"
        )

        st.markdown("---")
        col_rpe, col_date = st.columns(2)
        with col_rpe:
          rpe = st.slider(
              "RPE (1-10)",
              min_value=1.0,
              max_value=10.0,
              value=8.0,
              step=0.5,
              key="rpe_slider",
          )
        with col_date:
          log_date = st.date_input(
              "Workout Date", datetime.today(), key="lift_date"
          )

        submitted = st.form_submit_button("Save Workout Entry", type="primary")

        if submitted:
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
          "Outside Running",
          "Indoor Treadmill Run",
          "Keiser Bicycle",
          "Arc Trainer",
          "Assault Bike",
          "Rowing Machine",
          "Other",
      ]
      cardio_act = st.selectbox(
          "Cardio Activity", cardio_activity_options, key="cardio_act_sel"
      )
      if cardio_act == "Other":
        cardio_activity_name = st.text_input(
            "Type Cardio Activity", "Custom Cardio", key="custom_cardio_name"
        )
      else:
        cardio_activity_name = cardio_act

      with st.form("cardio_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
          cardio_dist = st.number_input(
              "Distance (km)",
              min_value=0.1,
              max_value=100.0,
              value=5.0,
              step=0.1,
              key="cardio_dist_input",
          )
        with c2:
          cardio_time = st.number_input(
              "Duration (mins)",
              min_value=1,
              max_value=600,
              value=30,
              step=1,
              key="cardio_time_input",
          )
        with c3:
          cardio_hr = st.number_input(
              "Avg Heart Rate (bpm)",
              min_value=0,
              max_value=220,
              value=145,
              step=1,
              key="cardio_hr_input",
          )

        if cardio_dist > 0:
          pace_mins = int(cardio_time // cardio_dist)
          pace_secs = int(((cardio_time / cardio_dist) - pace_mins) * 60)
          pace_str = f"{pace_mins}m {pace_secs}s / km"
        else:
          pace_str = "N/A"

        st.info(
            f"📊 **Cardio Summary:** Activity: **{cardio_activity_name}** |"
            f" Distance: **{cardio_dist} km** | Duration: **{cardio_time}"
            f" mins** | Pace: **{pace_str}** | HR:"
            f" **{cardio_hr if cardio_hr > 0 else 'N/A'} bpm**"
        )

        st.markdown("---")
        cardio_date = st.date_input(
            "Cardio Date", datetime.today(), key="cardio_date_input"
        )

        cardio_submitted = st.form_submit_button(
            "Save Cardio Entry", type="primary"
        )

        if cardio_submitted:
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

  # Call the isolated fragment function
  render_logger_fragment()

  st.markdown("---")
  st.subheader(f"📊 My Live Logs ({st.session_state.username})")

  sub_tab_prev1, sub_tab_prev2 = st.tabs(
      ["🏋️ Strength Workouts Log", "🏃 Cardio Sessions Log"]
  )

  with sub_tab_prev1:
    df_log = fetch_workouts(st.session_state.username)
    if not df_log.empty:
      st.dataframe(df_log.drop(columns=["id"]).head(50), use_container_width=True)

      # --- EDIT WORKOUT ENTRY EXPANDER ---
      with st.expander("✏️ Edit Workout Entries", expanded=False):
        workout_edit_options = dict(
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
        selected_workout_id = st.selectbox(
            "Select workout entry to edit",
            options=list(workout_edit_options.keys()),
            format_func=lambda x: workout_edit_options[x],
            key="edit_workout_sel",
        )

        if selected_workout_id:
          w_row = df_log[df_log["id"] == selected_workout_id].iloc[0]
          with st.form("edit_workout_form"):
            e_date = st.date_input(
                "Workout Date",
                datetime.strptime(w_row["Date"], "%Y/%m/%d").date(),
                key="edit_w_date",
            )
            e_routine = st.text_input(
                "Routine / Focus", value=w_row["Routine / Focus"]
            )
            e_exercise = st.text_input("Exercise", value=w_row["Exercise"])
            c1, c2, c3, c4 = st.columns(4)
            with c1:
              e_sets = st.number_input(
                  "Sets", min_value=1, value=int(w_row["Sets"])
              )
            with c2:
              e_reps = st.number_input(
                  "Reps", min_value=1, value=int(w_row["Reps"])
              )
            with c3:
              e_weight = st.text_input(
                  "Weight description", value=str(w_row["Weight (kg)"])
              )
            with c4:
              e_rpe = st.number_input(
                  "RPE", min_value=1.0, max_value=10.0, value=float(w_row["RPE (1-10)"])
              )

            col_upd, col_del = st.columns(2)
            with col_upd:
              update_w_btn = st.form_submit_button(
                  "Update Workout", type="primary"
              )
            with col_del:
              delete_w_btn = st.form_submit_button("Delete Workout")

            if update_w_btn:
              try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                                    UPDATE workouts 
                                    SET date = ?, routine = ?, exercise = ?, sets = ?, reps = ?, weight = ?, rpe = ?
                                    WHERE id = ? AND username = ?
                                """,
                    (
                        e_date.strftime("%Y/%m/%d"),
                        e_routine,
                        e_exercise,
                        int(e_sets),
                        int(e_reps),
                        e_weight,
                        float(e_rpe),
                        int(selected_workout_id),
                        st.session_state.username,
                    ),
                )
                conn.commit()
                st.cache_data.clear()
                st.success("Workout entry successfully updated!")
                st.rerun()
              except Exception as e:
                st.error(f"Error updating workout: {e}")

            if delete_w_btn:
              try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM workouts WHERE id = ? AND username = ?",
                    (int(selected_workout_id), st.session_state.username),
                )
                conn.commit()
                st.cache_data.clear()
                st.success("Workout entry deleted successfully!")
                st.rerun()
              except Exception as e:
                st.error(f"Error deleting workout: {e}")
    else:
      st.info("No strength workout logs found yet. Start logging above!")

  with sub_tab_prev2:
    df_cardio_log = fetch_cardio(st.session_state.username)
    if not df_cardio_log.empty:
      st.dataframe(df_cardio_log.drop(columns=["id"]).head(50), use_container_width=True)

      # --- EDIT CARDIO ENTRY EXPANDER ---
      with st.expander("✏️ Edit Cardio Entries", expanded=False):
        cardio_edit_options = dict(
            zip(
                df_cardio_log["id"],
                df_cardio_log["Date"]
                + " | "
                + df_cardio_log["Activity"]
                + " ("
                + df_cardio_log["Distance (km)"].astype(str)
                + " km)",
            )
        )
        selected_cardio_id = st.selectbox(
            "Select cardio entry to edit",
            options=list(cardio_edit_options.keys()),
            format_func=lambda x: cardio_edit_options[x],
            key="edit_cardio_sel",
        )

        if selected_cardio_id:
          c_row = df_cardio_log[df_cardio_log["id"] == selected_cardio_id].iloc[0]
          with st.form("edit_cardio_form"):
            ec_date = st.date_input(
                "Cardio Date",
                datetime.strptime(c_row["Date"], "%Y/%m/%d").date(),
                key="edit_c_date",
            )
            ec_activity = st.text_input("Activity", value=c_row["Activity"])
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
              ec_dist = st.number_input(
                  "Distance (km)", min_value=0.1, value=float(c_row["Distance (km)"])
              )
            with cc2:
              ec_dur = st.number_input(
                  "Duration (mins)", min_value=1, value=int(c_row["Duration (mins)"])
              )
            with cc3:
              ec_hr = st.number_input(
                  "Avg HR (bpm)", min_value=0, value=int(c_row["Avg HR (bpm)"])
              )

            col_updc, col_delc = st.columns(2)
            with col_updc:
              update_c_btn = st.form_submit_button(
                  "Update Cardio", type="primary"
              )
            with col_delc:
              delete_c_btn = st.form_submit_button("Delete Cardio")

            if update_c_btn:
              try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                                    UPDATE cardio 
                                    SET date = ?, activity = ?, distance = ?, duration = ?, avg_hr = ?
                                    WHERE id = ? AND username = ?
                                """,
                    (
                        ec_date.strftime("%Y/%m/%d"),
                        ec_activity,
                        float(ec_dist),
                        int(ec_dur),
                        int(ec_hr),
                        int(selected_cardio_id),
                        st.session_state.username,
                    ),
                )
                conn.commit()
                st.cache_data.clear()
                st.success("Cardio entry successfully updated!")
                st.rerun()
              except Exception as e:
                st.error(f"Error updating cardio: {e}")

            if delete_c_btn:
              try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM cardio WHERE id = ? AND username = ?",
                    (int(selected_cardio_id), st.session_state.username),
                )
                conn.commit()
                st.cache_data.clear()
                st.success("Cardio entry deleted successfully!")
                st.rerun()
              except Exception as e:
                st.error(f"Error deleting cardio: {e}")
    else:
      st.info("No cardio session logs found yet.")

# ==========================================
# PAGE 2: GOALS & WORKOUT PLAN
# ==========================================
elif selected_page == "🎯 Goals & Workout Plan":
  st.subheader("🎯 Athlete Goals & Target Settings")

  with st.form("goals_form"):
    st.session_state.goal = st.selectbox(
        "Primary Training Goal",
        [
            "Body Recomposition (Fat Loss & Muscle Gain)",
            "Hypertrophy (Maximum Muscle Mass)",
            "Strength & Powerlifting",
            "Fat Loss & Endurance",
            "General Fitness & Health",
        ],
        index=0
        if "Body Recomposition" in st.session_state.goal
        else 0,
    )

    colg1, colg2 = st.columns(2)
    with colg1:
      st.session_state.target_bw = st.number_input(
          "Target Body Weight (kg)",
          min_value=30.0,
          max_value=250.0,
          value=float(st.session_state.target_bw),
          step=0.5,
      )
    with colg2:
      st.session_state.target_bf = st.number_input(
          "Target Body Fat Percentage (%)",
          min_value=5.0,
          max_value=50.0,
          value=float(st.session_state.target_bf),
          step=0.5,
      )

    if st.form_submit_button("Save Goals & Targets", type="primary"):
      updated_profile = {
          "body_weight": st.session_state.body_weight,
          "gender": st.session_state.gender,
          "age": st.session_state.age,
          "height": st.session_state.height,
          "goal": st.session_state.goal,
          "target_bw": st.session_state.target_bw,
          "target_bf": st.session_state.target_bf,
          "last_seen_version": st.session_state.last_seen_version,
      }
      save_profile_db(st.session_state.username, updated_profile)
      st.success("Goals updated and synchronized to profile!")

  st.markdown("---")
  st.subheader("📋 Recommended Weekly Split")
  st.markdown("""
* **Day 1: Upper Body A** (Bench Press, Incline DB Press, Overhead Press, Lateral Raises, Triceps)
* **Day 2: Lower Body A** (Back Squat, Leg Press, Extensions, Hamstring Curls, RDLs, Calves)
* **Day 3: Upper Body B** (Lat Pulldowns, Seated Rows, Pull-ups, Barbell Rows, Face Pulls)
* **Day 4: Lower Body B** (Bulgarian Split Squats, Goblet Squats, Leg Extensions, RDLs, Calves)
* **Day 5: Core & Cardio** (Ab Machines, Cable Crunches, Hanging Leg Raises, Keiser Bicycle)
""")

# ==========================================
# PAGE 3: BODY WEIGHT TRACKER
# ==========================================
elif selected_page == "⚖️ Body Weight Tracker":
  st.subheader("⚖️ Body Weight Progress & Trend Tracker")

  with st.form("bw_form"):
    colw1, colw2, colw3 = st.columns(3)
    with colw1:
      log_bw = st.number_input(
          "Body Weight (kg)",
          min_value=30.0,
          max_value=250.0,
          value=float(st.session_state.body_weight),
          step=0.1,
      )
    with colw2:
      log_bw_date = st.date_input("Date", datetime.today())
    with colw3:
      log_bw_notes = st.text_input("Notes (e.g., Morning weigh-in)", "Morning fasting")

    if st.form_submit_button("Log Body Weight", type="primary"):
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
                log_bw_date.strftime("%Y/%m/%d"),
                float(log_bw),
                log_bw_notes,
            ),
        )
        conn.commit()
        st.cache_data.clear()
        st.success(f"Successfully logged body weight: {log_bw}kg!")
        st.rerun()
      except Exception as e:
        st.error(f"Error logging body weight: {e}")

  df_bw = fetch_body_weight(st.session_state.username)
  if not df_bw.empty:
    st.markdown("---")
    st.subheader("📈 Body Weight Chart")
    chart_df = df_bw.set_index("Date")[["Body Weight (kg)"]]
    st.line_chart(chart_df)

    st.markdown("---")
    st.subheader("📋 Weight Logs History")
    st.dataframe(df_bw.drop(columns=["id"]), use_container_width=True)
  else:
    st.info("No body weight entries recorded yet. Add your first entry above!")

# ==========================================
# PAGE 4: PROGRESS & ANALYTICS
# ==========================================
elif selected_page == "📈 Progress & Analytics":
  st.subheader("📈 Training Volume & Performance Analytics")
  df_analytics_workouts = fetch_workouts(st.session_state.username)

  if not df_analytics_workouts.empty:
    total_workouts_logged = len(df_analytics_workouts)
    unique_routines_count = df_analytics_workouts["Routine / Focus"].nunique()

    col_m1, col_m2 = st.columns(2)
    with col_m1:
      st.metric("Total Exercise Entries Logged", total_workouts_logged)
    with col_m2:
      st.metric("Unique Routines Focused On", unique_routines_count)

    st.markdown("---")
    st.subheader("🔍 Exercise Progression Breakdown")
    selected_ex_filter = st.selectbox(
        "Select Exercise to Inspect",
        df_analytics_workouts["Exercise"].unique(),
    )
    ex_filtered_df = df_analytics_workouts[
        df_analytics_workouts["Exercise"] == selected_ex_filter
    ].sort_values("Date")
    st.dataframe(ex_filtered_df.drop(columns=["id"]), use_container_width=True)
  else:
    st.info("Log some workout entries to unlock advanced analytics and progress charts!")

# ==========================================
# PAGE 5: GLOSSARY & FEEDBACK
# ==========================================
elif selected_page == "📖 Glossary & Feedback":
  st.subheader("📖 Training Glossary & Developer Feedback")

  with st.expander("📚 Fitness & Lifting Terminology Glossary", expanded=False):
    st.markdown("""
* **RPE (Rate of Perceived Exertion):** A scale from 1 to 10 estimating how many reps you had left in the tank (10 = absolute failure).
* **Volume:** Total amount of weight lifted calculated as $Sets \\times Reps \\times Weight$.
* **Body Recomposition:** The simultaneous process of building muscle mass while losing body fat.
""")

  st.markdown("---")
  st.subheader("💬 Send Feedback or Feature Request to Developer")
  with st.form("feedback_form"):
    f_tester = st.text_input("Your Name", value=st.session_state.username)
    f_rating = st.slider("App Experience Rating (1-5)", 1, 5, 5)
    f_cat = st.selectbox(
        "Category",
        [
            "General Feedback",
            "Bug Report",
            "Feature Request",
            "UI / UX Improvement",
        ],
    )
    f_msg = st.text_area(
        "Your Message / Suggestion",
        placeholder="Type your feedback or bug report here...",
    )

    if st.form_submit_button("Submit Feedback", type="primary"):
      if not f_msg.strip():
        st.warning("Please type a message before submitting.")
      else:
        try:
          conn = get_db_connection()
          cursor = conn.cursor()
          now_dt = datetime.now()
          cursor.execute(
              """
                            INSERT INTO reviews (date, time, tester_name, rating, category, message)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
              (
                  now_dt.strftime("%Y/%m/%d"),
                  now_dt.strftime("%H:%M:%S"),
                  f_tester,
                  int(f_rating),
                  f_cat,
                  f_msg,
              ),
          )
          conn.commit()
          st.success("Thank you! Your feedback has been sent to the developer.")
        except Exception as e:
          st.error(f"Error submitting feedback: {e}")

# ==========================================
# PAGE 6: ADMIN DASHBOARD
# ==========================================
elif selected_page == "🔒 Admin Dashboard":
  st.subheader("🔒 Administrator & Database Diagnostic Dashboard")

  admin_pin = st.text_input("Enter Admin PIN", type="password")

  if admin_pin == "2026":
    st.success("Admin Access Granted.")
    st.markdown("---")

    sub_adm1, sub_adm2, sub_adm3 = st.tabs(
        ["👥 Registered User Profiles", "💬 User Feedback / Reviews", "⚙️ Database Control"]
    )

    with sub_adm1:
      st.markdown("### 👥 Registered User Profiles")
      try:
        conn = get_db_connection()
        df_profiles = pd.read_sql_query(
            "SELECT username, body_weight, gender, age, height, goal, target_bw,"
            " target_bf, last_seen_version FROM profiles",
            conn,
        )
        if not df_profiles.empty:
          st.dataframe(df_profiles, use_container_width=True)
        else:
          st.warning("No registered user profiles found in database.")
      except Exception as e:
        st.error(f"Error fetching profiles: {e}")

    with sub_adm2:
      st.markdown("### 💬 User Reviews & Submissions")
      try:
        conn = get_db_connection()
        df_reviews = pd.read_sql_query("SELECT * FROM reviews ORDER BY id DESC", conn)
        if not df_reviews.empty:
          st.dataframe(df_reviews, use_container_width=True)
        else:
          st.info("No reviews submitted yet.")
      except Exception as e:
        st.error(f"Error loading reviews: {e}")

    with sub_adm3:
      st.markdown("### ⚙️ Database Diagnostics & Reset Control")
      st.warning(
          "⚠️ **Danger Zone:** Resetting the database drops all tables and re-seeds"
          " initial default structures."
      )

      confirm_reset = st.checkbox(
          "I understand this will permanently delete ALL user data across the"
          " suite."
      )
      if st.button("⚠️ Reset Entire Database", type="primary"):
        if confirm_reset:
          reset_database()
          st.success("Database completely reset and re-initialized!")
          st.rerun()
        else:
          st.error(
              "Please check the confirmation box above to authorize a full database"
              " reset."
          )

  elif admin_pin != "":
    st.error("Incorrect Admin PIN.")

# ==========================================
# PAGE 7: WHAT'S NEW LOG
# ==========================================
elif selected_page == "📢 What's New Log":
  st.subheader("📢 Release Notes & What's New Log")

  for ver, bullets in CHANGELOG.items():
    with st.expander(f"Version {ver}", expanded=(ver == CURRENT_VERSION)):
      for bullet in bullets:
        st.markdown(f"- {bullet}")
