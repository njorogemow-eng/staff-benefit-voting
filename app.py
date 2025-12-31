import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta

# ================= TIMEZONE =================
KENYA_TZ = timezone(timedelta(hours=3))
VOTING_DEADLINE = datetime(2026, 1, 16, 23, 59, tzinfo=KENYA_TZ)

# ================= ADMIN =================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"  # CHANGE THIS

# ================= VALID EMPLOYEE IDS =================
VALID_IDS = {f"OLK{str(i).zfill(3)}" for i in range(1, 401)}

# ================= DATABASE =================
conn = sqlite3.connect("votes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS votes (
    emp_id TEXT PRIMARY KEY,
    name TEXT,
    location TEXT,
    reg_fee TEXT,
    monthly TEXT,
    time TEXT
)
""")
conn.commit()

# ================= HELPERS =================
def voting_open():
    return datetime.now(KENYA_TZ) <= VOTING_DEADLINE

def countdown():
    remaining = VOTING_DEADLINE - datetime.now(KENYA_TZ)
    if remaining.total_seconds() <= 0:
        return "❌ Voting closed"
    return f"⏳ Voting closes in {remaining.days} days"

def fetch_votes():
    return pd.read_sql("SELECT * FROM votes", conn)

# ================= CHARTS =================
def pie_chart(df, title):
    fig, ax = plt.subplots()
    if df.empty:
        ax.text(0.5, 0.5, "No votes", ha="center")
        return fig

    counts = df.value_counts()
    ax.pie(counts, labels=counts.index, autopct="%1.0f%%", startangle=90)
    ax.set_title(title)
    return fig

# ================= ACTIONS =================
def submit_vote(emp_id, name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", *load_results()

    if emp_id not in VALID_IDS:
        return "❌ Invalid Employee ID.", *load_results()

    cursor.execute("SELECT emp_id FROM votes WHERE emp_id=?", (emp_id,))
    if cursor.fetchone():
        return "❌ You have already voted.", *load_results()

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (emp_id, name, location, reg_fee, monthly, str(datetime.now(KENYA_TZ)))
    )
    conn.commit()

    return "✅ Vote submitted successfully.", *load_results()

def load_results():
    df = fetch_votes()

    return (
        pie_chart(df["reg_fee"], "Registration Fee Vote"),
        pie_chart(df["monthly"], "Monthly Contribution"),
        pie_chart(df[df["location"]=="Nairobi"]["monthly"], "Nairobi Votes"),
        pie_chart(df[df["location"]=="Amboseli"]["monthly"], "Amboseli Votes"),
        pie_chart(df[df["location"]=="Mara"]["monthly"], "Mara Votes"),
    )

def admin_export(user, pwd):
    if user != ADMIN_USER or pwd != ADMIN_PASS:
        return None
    df = fetch_votes()
    file = "voting_results.xlsx"
    df.to_excel(file, index=False)
    return file

def admin_clear(user, pwd):
    if user != ADMIN_USER or pwd != ADMIN_PASS:
        return "❌ Invalid admin credentials"
    cursor.execute("DELETE FROM votes")
    conn.commit()
    return "✅ All votes cleared"

# ================= UI =================
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue")) as demo:
    gr.Markdown("## 🗳️ Staff Benefit Scheme – Live Voting")
    gr.Markdown(f"**🇰🇪 Kenya Time:** {datetime.now(KENYA_TZ).strftime('%d %b %Y %H:%M')}")
    gr.Markdown(f"### {countdown()}")

    with gr.Tab("Vote"):
        emp_id = gr.Textbox(label="Employee ID (OLK001 – OLK400)")
        name = gr.Textbox(label="Full Name")
        location = gr.Dropdown(["Nairobi", "Amboseli", "Mara"], label="Location")
        reg_fee = gr.Dropdown(["Yes", "No"], label="Introduce Registration Fee (KES 200)")
        monthly = gr.Dropdown(["500 KSH", "1000 KSH"], label="Monthly Contribution")

        submit = gr.Button("Submit Vote", variant="primary")
        status = gr.Textbox(label="Status", interactive=False)

        reg_chart = gr.Plot()
        monthly_chart = gr.Plot()
        nairobi_chart = gr.Plot()
        amboseli_chart = gr.Plot()
        mara_chart = gr.Plot()

        submit.click(
            submit_vote,
            inputs=[emp_id, name, location, reg_fee, monthly],
            outputs=[status, reg_chart, monthly_chart, nairobi_chart, amboseli_chart, mara_chart]
        )

        demo.load(load_results, outputs=[
            reg_chart, monthly_chart, nairobi_chart, amboseli_chart, mara_chart
        ])

    with gr.Tab("Admin"):
        gr.Markdown("### 🔐 Admin Panel")
        admin_user = gr.Textbox(label="Username")
        admin_pass = gr.Textbox(label="Password", type="password")

        export_btn = gr.Button("⬇ Download Results (Excel)")
        clear_btn = gr.Button("🗑 Clear All Votes", variant="stop")

        file_out = gr.File()
        clear_msg = gr.Textbox(interactive=False)

        export_btn.click(admin_export, inputs=[admin_user, admin_pass], outputs=file_out)
        clear_btn.click(admin_clear, inputs=[admin_user, admin_pass], outputs=clear_msg)

demo.launch(server_name="0.0.0.0", server_port=7860)
