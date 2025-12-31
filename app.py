import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime
import pytz

# ================== SETTINGS ==================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

KENYA_TZ = pytz.timezone("Africa/Nairobi")
VOTING_DEADLINE = KENYA_TZ.localize(datetime(2026, 1, 16, 23, 59))

VALID_IDS = {f"OLK{str(i).zfill(3)}" for i in range(1, 401)}

# ================== DATABASE ==================
conn = sqlite3.connect("votes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS votes (
    member_id TEXT PRIMARY KEY,
    full_name TEXT,
    location TEXT,
    reg_fee TEXT,
    monthly TEXT,
    timestamp TEXT
)
""")
conn.commit()

# ================== HELPERS ==================
def kenya_now():
    return datetime.now(KENYA_TZ)

def voting_open():
    return kenya_now() <= VOTING_DEADLINE

def days_left():
    delta = VOTING_DEADLINE - kenya_now()
    return max(delta.days, 0)

def load_votes():
    return pd.read_sql("SELECT * FROM votes", conn)

# ================== VOTING ==================
def submit_vote(member_id, full_name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", results_table(), charts()[0], charts()[1]

    if member_id not in VALID_IDS:
        return "❌ Invalid Employee ID. Use OLK001 – OLK400.", results_table(), charts()[0], charts()[1]

    cursor.execute("SELECT 1 FROM votes WHERE member_id=?", (member_id,))
    if cursor.fetchone():
        return "❌ This Employee ID has already voted.", results_table(), charts()[0], charts()[1]

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (member_id, full_name, location, reg_fee, monthly, str(kenya_now()))
    )
    conn.commit()

    return "✅ Vote submitted successfully.", results_table(), charts()[0], charts()[1]

# ================== RESULTS ==================
def results_table():
    df = load_votes()
    return df.groupby("location").size().reset_index(name="Votes")

def charts():
    df = load_votes()
    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()

    if df.empty:
        ax1.text(0.5, 0.5, "No votes yet", ha="center")
        ax2.text(0.5, 0.5, "No votes yet", ha="center")
        return fig1, fig2

    df["reg_fee"].value_counts().plot.pie(
        autopct="%1.0f%%", ax=ax1, title="Registration Fee Vote"
    )

    df["monthly"].value_counts().plot.pie(
        autopct="%1.0f%%", ax=ax2, title="Monthly Contribution Vote"
    )

    return fig1, fig2

# ================== ADMIN ==================
def admin_login(user, pwd):
    return user == ADMIN_USER and pwd == ADMIN_PASS

def export_excel(user, pwd):
    if not admin_login(user, pwd):
        return None
    file = "voting_results.xlsx"
    load_votes().to_excel(file, index=False)
    return file

def clear_votes(user, pwd):
    if not admin_login(user, pwd):
        return "❌ Unauthorized"
    cursor.execute("DELETE FROM votes")
    conn.commit()
    return "✅ All votes cleared"

# ================== UI ==================
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue")) as demo:
    gr.Markdown("""
    # 🗳️ Staff Benefit Scheme Voting  
    **Kenya Time:** """ + kenya_now().strftime("%d %B %Y, %H:%M") + f"""  
    ⏳ **Voting closes in {days_left()} days**
    """)

    with gr.Tab("Vote"):
        member_id = gr.Textbox(label="Employee ID (OLK001 – OLK400)")
        full_name = gr.Textbox(label="Full Name")
        location = gr.Dropdown(["Nairobi", "Amboseli", "Mara"], label="Location")
        reg_fee = gr.Dropdown(["Yes", "No"], label="Introduce Registration Fee (KES 200)")
        monthly = gr.Dropdown(["500 KSH", "1000 KSH"], label="Monthly Contribution")

        submit = gr.Button("Submit Vote")
        status = gr.Textbox(label="Status", interactive=False)

        table = gr.Dataframe(label="Votes per Location", interactive=False)
        pie1 = gr.Plot()
        pie2 = gr.Plot()

        submit.click(
            submit_vote,
            inputs=[member_id, full_name, location, reg_fee, monthly],
            outputs=[status, table, pie1, pie2]
        )

        demo.load(results_table, outputs=table)
        demo.load(lambda: charts()[0], outputs=pie1)
        demo.load(lambda: charts()[1], outputs=pie2)

    with gr.Tab("Admin"):
        admin_user = gr.Textbox(label="Admin Username")
        admin_pass = gr.Textbox(label="Admin Password", type="password")

        export_btn = gr.Button("Download Results (Excel)")
        clear_btn = gr.Button("Clear All Votes")

        file_out = gr.File()
        clear_msg = gr.Textbox()

        export_btn.click(export_excel, [admin_user, admin_pass], file_out)
        clear_btn.click(clear_votes, [admin_user, admin_pass], clear_msg)

demo.launch(server_name="0.0.0.0", server_port=7860)
