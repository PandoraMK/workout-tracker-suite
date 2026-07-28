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


def get_db_connection():
  """Returns a fresh, thread-safe database connection for each operation."""
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

  # 5. Profiles Table (Per-user settings with secure password protection)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
            password TEXT,
            body_weight REAL,
            gender TEXT,
            age INTEGER,
            height REAL
        )
    """)
  cursor.execute("PRAGMA table_info(profiles)")
  profile_cols = [col[1] for col in cursor.fetchall()]
  if "password" not in profile_cols:
    cursor.execute("ALTER TABLE profiles ADD COLUMN password TEXT")

  cursor.execute("""
        INSERT OR IGNORE INTO profiles (username, password, body_weight, gender, age, height)
        VALUES ('Modiri', '2026', 88.0, 'Male', 25, 178.0)
    """)

  conn.commit()
  conn.close()


init_db()


# --- HELPER FUNCTIONS ---
def load_profile(username):
  conn = get_db_connection()
  try:
    df = pd.read_sql_query(
        "SELECT body_weight, gender, age, height FROM profiles WHERE username = ?",
        conn,
        params=(username,),
    )
    if not df.empty:
      return {
          "body_weight": float(df["body_weight"].iloc[0]),
          "gender": df["gender"].iloc[0],
          "age": int(df["age"].iloc[0]),
          "height": float(df["height"].iloc[0]),
      }
  except Exception:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT body_weight, gender, age, height FROM profiles WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    if row:
      return {
          "body_weight": row[0],
          "gender": row[1],
          "age": row[2],
          "height": row[3],
      }
  finally:
    conn.close()
  return {"body_weight": 75.0, "gender": "Male", "age": 25, "height": 175.0}


def save_profile_db(username, profile_data):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        UPDATE profiles 
        SET body_weight = ?, gender = ?, age = ?, height = ?
        WHERE username = ?
    """,
      (
          profile_data["body_weight"],
          profile_data["gender"],
          profile_data["age"],
          profile_data["height"],
          username,
      ),
  )
  conn.commit()
  conn.close()


# --- SESSION STATE INITIALIZATION & PROFILE PRE-LOADING ---
if "username" not in st.session_state:
  st.session_state.username = None
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

# Pre-load profile into session state BEFORE widgets are instantiated
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

st.set_page_config(
    page_title="Workout Master Suite", page_icon="💪", layout="centered"
)

# --- SIDEBAR FOR UNIQUE USER LOGIN & PROFILE SETTINGS ---
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
            conn.close()
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
                            INSERT INTO profiles (username, password, body_weight, gender, age, height)
                            VALUES (?, ?, 75.0, 'Male', 25, 175.0)
                        """,
                (u_clean, p_clean),
            )
            conn.commit()
            conn.close()

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
          "SELECT username, body_weight, gender, age, height FROM profiles"
          " WHERE username = ?",
          conn,
          params=(st.session_state.username,),
      )
      conn.close()

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
    f" {st.session_state.body_weight}kg) with cloud multi-device sync."
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
  st.subheader("Add Workout or Cardio Activity")

  log_type = st.radio(
      "Select Activity Type to Log",
      ["🏋️ Strength & Bodyweight Workout", "🏃 Cardio Session"],
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
          "Select Exercise", available_exercises + ["Other (Type Below)"]
      )
      if exercise_choice == "Other (Type Below)":
        exercise_name = st.text_input("Type Exercise Name", "New Exercise")
      else:
        exercise_name = exercise_choice

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
      else:
        st.markdown("""
                * **Pre-Workout Dynamic Stretches:** Arm circles, leg swings, light bodyweight movements.
                * **Post-Workout Static Stretches:** Full body static stretches focusing on worked muscle groups.
                """)

    st.markdown("---")
    st.write("🏋️ **Set & Weight Progression (Pyramids / Weight Changes)**")

    num_blocks = st.selectbox(
        "How many different weight blocks?", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=0
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
        conn.close()

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
          "Avg Heart Rate (bpm)", min_value=0, max_value=220, value=145, step=1
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
        conn.close()

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
    try:
      conn = get_db_connection()
      df_log = pd.read_sql_query(
          "SELECT id, date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts WHERE username = ? ORDER BY id DESC",
          conn,
          params=(st.session_state.username,),
      )
      conn.close()

      if not df_log.empty:
        st.dataframe(df_log.drop(columns=["id"]).head(10), use_container_width=True)

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
                conn.close()

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
    except Exception as e:
      st.info(f"Could not load workout log preview: {e}")

  with sub_tab_prev2:
    try:
      conn = get_db_connection()
      df_cardio_log = pd.read_sql_query(
          "SELECT id, date AS Date, activity AS Activity, distance AS"
          " 'Distance (km)', duration AS 'Duration (mins)', avg_hr AS 'Avg HR"
          " (bpm)', pace AS Pace FROM cardio WHERE username = ? ORDER BY id"
          " DESC",
          conn,
          params=(st.session_state.username,),
      )
      conn.close()

      if not df_cardio_log.empty:
        st.dataframe(
            df_cardio_log.drop(columns=["id"]).head(10), use_container_width=True
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
                conn.close()

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
    except Exception as e:
      st.info(f"Could not load cardio log preview: {e}")

with tab2:
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
        conn.close()

        st.success(
            f"Successfully recorded body weight: {logged_bw} kg saved for"
            f" {st.session_state.username}!"
        )
      except Exception as e:
        st.error(f"Error saving body weight: {e}")

  st.markdown("---")
  st.subheader("📈 Body Weight Trend & Management")
  try:
    conn = get_db_connection()
    df_bw = pd.read_sql_query(
        "SELECT id, date AS Date, body_weight AS 'Body Weight (kg)', notes AS"
        " Notes FROM body_weight WHERE username = ? ORDER BY date ASC",
        conn,
        params=(st.session_state.username,),
    )
    conn.close()

    if not df_bw.empty:
      st.dataframe(df_bw.drop(columns=["id"]), use_container_width=True)
      chart_bw_data = df_bw[["Date", "Body Weight (kg)"]].dropna()
      if not chart_bw_data.empty:
        st.markdown("### Weight Progression Chart")
        st.line_chart(
            chart_bw_data.set_index("Date"), use_container_width=True
        )

      with st.expander(
          "🗑️ Manage & Delete Body Weight Entries", expanded=False
      ):
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
            "Delete Selected Body Weight Entries",
            type="primary",
            key="btn_del_bw",
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
              conn.close()

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
      st.info(
          f"No body weight entries logged for {st.session_state.username} yet."
      )
  except Exception as e:
    st.info(f"Could not load body weight chart: {e}")

with tab3:
  st.subheader(f"📈 Training Analytics ({st.session_state.username})")

  an_tab1, an_tab2 = st.tabs(
      ["🏋️ Strength Analytics", "🏃 Cardio Performance Analytics"]
  )

  with an_tab1:
    try:
      conn = get_db_connection()
      df_analytics = pd.read_sql_query(
          "SELECT date AS Date, routine AS 'Routine / Focus', exercise AS"
          " Exercise, sets AS Sets, reps AS Reps, weight AS 'Weight (kg)',"
          " total_volume AS 'Total Volume (kg)', rpe AS 'RPE (1-10)' FROM"
          " workouts WHERE username = ? ORDER BY id ASC",
          conn,
          params=(st.session_state.username,),
      )
      conn.close()

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
        st.info("Add strength workout entries to generate performance charts.")
    except Exception as e:
      st.info(f"Error loading strength charts: {e}")

  with an_tab2:
    try:
      conn = get_db_connection()
      df_cardio_an = pd.read_sql_query(
          "SELECT date AS Date, activity AS Activity, distance AS"
          " 'Distance (km)', duration AS 'Duration (mins)', avg_hr AS 'Avg HR"
          " (bpm)', pace AS Pace FROM cardio WHERE username = ? ORDER BY id"
          " ASC",
          conn,
          params=(st.session_state.username,),
      )
      conn.close()

      if not df_cardio_an.empty:
        st.markdown("### Cardio Distance Over Time")
        cardio_chart_data = df_cardio_an[["Date", "Distance (km)"]].dropna()
        if not cardio_chart_data.empty:
          st.line_chart(
              cardio_chart_data.set_index("Date"), use_container_width=True
          )

        st.markdown("---")
        st.markdown("### Cardio Logs History")
        st.dataframe(df_cardio_an, use_container_width=True)
      else:
        st.info("Log cardio sessions to view performance analytics!")
    except Exception as e:
      st.info(f"Error loading cardio charts: {e}")

with tab4:
  st.subheader("📖 Glossary & Definitions")
  st.markdown("""
  * **RPE (Rate of Perceived Exertion):** A scale from 1 to 10 measuring how intense a set felt. 10 is absolute failure, while 7-8 leaves 2-3 reps in reserve (RIR).
  * **Total Volume:** The total weight lifted calculated as Sets × Reps × Weight. Used to track progressive overload over time.
  * **Pace:** The time taken per kilometer during a cardio session, automatically calculated from distance and duration.
  * **Body Recomposition:** The simultaneous process of building muscle mass while reducing body fat percentage.
  """)

with tab5:
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
        conn.close()

        st.success("Thank you! Your feedback has been successfully submitted.")
      except Exception as e:
        st.error(f"Error submitting review: {e}")

  st.markdown("---")
  st.subheader("🔒 Admin Dashboard (Maker Only)")
  st.write(
      "Enter the Admin PIN to view incoming user reviews and feedback history."
  )

  admin_pin = st.text_input("Admin PIN", type="password", key="admin_pin_input")

  if admin_pin == "2026":
    st.success("Admin access granted!")
    try:
      conn = get_db_connection()
      df_reviews = pd.read_sql_query(
          "SELECT date AS Date, time AS Time, tester_name AS 'Tester', rating AS"
          " 'Rating (1-5)', category AS Category, message AS Message FROM"
          " reviews ORDER BY id DESC",
          conn,
      )
      conn.close()

      if not df_reviews.empty:
        st.dataframe(df_reviews, use_container_width=True)
      else:
        st.info("No reviews submitted yet.")
    except Exception as e:
      st.info(f"Could not load reviews: {e}")
  elif admin_pin != "":
    st.error("Incorrect Admin PIN.")
  else:
    st.info("Please enter your Admin PIN to unlock the review history table.")
