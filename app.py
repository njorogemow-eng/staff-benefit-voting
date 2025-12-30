import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime
import pytz

# ================= TIMEZONE =================
KENYA_TZ = pytz.timezone("Africa/Nairobi")

# ================= SETTINGS =================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# Voting closes: 16 Jan 2026, 23:59 Kenya time
VOTING_DEADLINE = KENYA_TZ.localize(datetime(2026, 1, 16, 23, 59))
manual_close = False

# ================= DATABASE =================
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

# ================= MEMBERS =================
members_df = pd.read_csv("members.csv")
valid_members = set(members_df["MemberID"].astype(str))

# ================= HELPERS =================
def kenya_now():
    return datetime.now(KENYA_TZ)

def voting_open():
    return kenya_now() <= VOTING_DEADLINE and not manual_close

def countdown_text():
    remaining = VOTING_DEADLINE - kenya_now()
    if remaining.total_seconds() <= 0:
        return "❌ Voting is CLOSED"
    days = remaining.days
    hours = remaining.seconds // 3600
    return f"⏳ Voting closes in {days} days, {hours} hours (Kenya Time)"

# ================= RESULTS =================
def results_table():
    df = pd.read_sql("SELECT * FROM votes", conn)
    return pd.DataFrame({
        "Item": ["Registration Fee", "Registration Fee", "Monthly Contribution", "Monthly Contribution"],
        "Option": ["Yes", "No", "500 KSH", "1000 KSH"],
        "Votes": [
            (df["reg_fee"] == "Yes").sum() if not df.empty else 0,
            (df["reg_fee"] == "No").sum() if not df.empty else 0,
            (df["monthly"] == "500 KSH").sum() if not df.empty else 0,
            (df["monthly"] == "1000 KSH").sum() if not df.empty else 0
        ]
    })

def chart_plot():
    df = pd.read_sql("SELECT * FROM votes", conn)
    fig, ax = plt.subplots()
    if df.empty:
        ax.text(0.5, 0.5, "No votes yet", ha="center")
        return fig

    counts = {
        "Yes": (df["reg_fee"] == "Yes").sum(),
        "No": (df["reg_fee"] == "No").sum(),
        "500 KSH": (df["monthly"] == "500 KSH").sum(),
        "1000 KSH": (df["monthly"] == "1000 KSH").sum()
    }
    ax.bar(counts.keys(), counts.values())
    ax.set_title("Live Voting Results")
    return fig

# ================= VOTING =================
def submit_vote(member_id, full_name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", results_table(), chart_plot(), countdown_text()

    if member_id not in valid_members:
        return "❌ Invalid Member ID.", results_table(), chart_plot(), countdown_text()

    cursor.execute("SELECT 1 FROM votes WHERE member_id=?", (member_id,))
    if cursor.fetchone():
        return "❌ You have already voted.", results_table(), chart_plot(), countdown_text()

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (member_id, full_name, location, reg_fee, monthly, kenya_now().isoformat())
    )
    conn.commit()

    return "✅ Vote submitted successfully.", results_table(), chart_plot(), countdown_text()

# ================= ADMIN =================
def admin_close(user, password):
    global manual_close
    if user == ADMIN_USER and password == ADMIN_PASS:
        manual_close = True
        return "✅ Voting manually closed."
    return "❌ Invalid admin credentials."

def export_excel(user, password):
    if user != ADMIN_USER or password != ADMIN_PASS:
        return None
    df = pd.read_sql("SELECT * FROM votes", conn)
    file = "voting_results.xlsx"
    df.to_excel(file, index=False)
    return file

# ================= UI =================
with gr.Blocks(title="Staff Benefit Voting") as demo:
    gr.Markdown("# 🗳️ Staff Benefit Scheme – Live Voting")
    gr.Markdown("🕒 **Current Time (Kenya):** " + kenya_now().strftime("%d %B %Y, %H:%M"))
    countdown = gr.Markdown(countdown_text())

    with gr.Tab("Vote"):
        member_id = gr.Textbox(label="Member ID")
        full_name = gr.Textbox(label="Full Name")
        location = gr.Dropdown(["Nairobi", "Amboseli", "Mara"], label="Location")
        reg_fee = gr.Dropdown(["Yes", "No"], label="Registration Fee (KES 200)")
        monthly = gr.Dropdown(["500 KSH", "1000 KSH"], label="Monthly Contribution")

        submit = gr.Button("Submit Vote")
        status = gr.Textbox(label="Status", interactive=False)
        results = gr.Dataframe(interactive=False)
        chart = gr.Plot()

        submit.click(
            submit_vote,
            inputs=[member_id, full_name, location, reg_fee, monthly],
            outputs=[status, results, chart, countdown]
        )

        demo.load(results_table, outputs=results)
        demo.load(chart_plot, outputs=chart)

    with gr.Tab("Admin"):
        admin_user = gr.Textbox(label="Admin Username")
        admin_pass = gr.Textbox(label="Admin Password", type="password")
        close_btn = gr.Button("Close Voting Now")
        close_status = gr.Textbox(interactive=False)
        export_btn = gr.Button("Export Results to Excel")
        file_out = gr.File()

        close_btn.click(admin_close, [admin_user, admin_pass], close_status)
        export_btn.click(export_excel, [admin_user, admin_pass], file_out)

demo.launch(server_name="0.0.0.0", server_port=7860)
