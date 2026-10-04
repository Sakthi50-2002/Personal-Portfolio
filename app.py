import os
import csv
import io
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    jsonify,
    send_file
)

from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

# IMPORTANT:
# Set PORTFOLIO_SECRET_KEY in your computer environment.
app.secret_key = os.environ.get(
    "PORTFOLIO_SECRET_KEY",
    "development-only-change-this-secret"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "portfolio.db")

BACKUP_FOLDER = os.path.join(
    BASE_DIR,
    "database_backups"
)

os.makedirs(BACKUP_FOLDER, exist_ok=True)


# =========================================================
# ADMIN CONFIGURATION
# =========================================================

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "Admin@123"
)

ADMIN_ROLE = "Super Admin"


# =========================================================
# SECURITY SETTINGS
# =========================================================

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 5

MAX_CONTACT_MESSAGES = 3
CONTACT_TIME_WINDOW = 60


failed_login_attempts = {}
contact_rate_limit = {}


# =========================================================
# INDIA TIME
# =========================================================

def india_time():
    """
    Returns current India Standard Time.
    UTC + 5:30
    """

    utc_now = datetime.now(timezone.utc)

    india_now = utc_now + timedelta(
        hours=5,
        minutes=30
    )

    return india_now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    conn = get_db_connection()

    cursor = conn.cursor()

    # -----------------------------------------------------
    # Messages table
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL,

            message TEXT NOT NULL,

            created_at TEXT,

            category TEXT DEFAULT 'Normal',

            risk_level TEXT DEFAULT 'Low',

            sentiment TEXT DEFAULT 'Neutral',

            analysis_reason TEXT
        )
    """)

    # -----------------------------------------------------
    # Activity logs table
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            action TEXT NOT NULL,

            created_at TEXT
        )
    """)

    # -----------------------------------------------------
    # Check existing message columns
    # -----------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(messages)"
    )

    columns = [
        row["name"]
        for row in cursor.fetchall()
    ]

    required_columns = {

        "created_at": "TEXT",

        "category": "TEXT DEFAULT 'Normal'",

        "risk_level": "TEXT DEFAULT 'Low'",

        "sentiment": "TEXT DEFAULT 'Neutral'",

        "analysis_reason": "TEXT"
    }

    for column, definition in required_columns.items():

        if column not in columns:

            cursor.execute(
                f"ALTER TABLE messages ADD COLUMN {column} {definition}"
            )

    # -----------------------------------------------------
    # Update missing values
    # -----------------------------------------------------

    cursor.execute("""
        UPDATE messages

        SET created_at = ?

        WHERE created_at IS NULL
    """, (india_time(),))

    cursor.execute("""
        UPDATE messages

        SET category = 'Normal'

        WHERE category IS NULL
    """)

    cursor.execute("""
        UPDATE messages

        SET risk_level = 'Low'

        WHERE risk_level IS NULL
    """)

    cursor.execute("""
        UPDATE messages

        SET sentiment = 'Neutral'

        WHERE sentiment IS NULL
    """)

    conn.commit()

    conn.close()


# =========================================================
# ACTIVITY LOG
# =========================================================

def log_activity(action):

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO activity_logs
        (
            action,
            created_at
        )

        VALUES (?, ?)
    """, (
        action,
        india_time()
    ))

    conn.commit()

    conn.close()


# =========================================================
# AI-STYLE MESSAGE ANALYSIS
# =========================================================

def analyze_message(message):

    text = message.lower()

    # -----------------------------------------------------
    # Spam keywords
    # -----------------------------------------------------

    spam_keywords = [

        "free money",
        "winner",
        "lottery",
        "claim prize",
        "prize",
        "click here",
        "urgent offer",
        "limited offer",
        "buy now",
        "crypto",
        "bitcoin",
        "investment",
        "double your money",
        "send money",
        "cash prize",
        "congratulations you won",
        "100% profit",
        "earn money fast"
    ]

    # -----------------------------------------------------
    # Important keywords
    # -----------------------------------------------------

    important_keywords = [

        "project",
        "job",
        "interview",
        "business",
        "collaboration",
        "hire",
        "developer",
        "freelance",
        "urgent",
        "meeting",
        "opportunity",
        "work"
    ]

    # -----------------------------------------------------
    # Positive keywords
    # -----------------------------------------------------

    positive_words = [

        "good",
        "great",
        "excellent",
        "thank",
        "thanks",
        "amazing",
        "awesome",
        "nice",
        "happy",
        "love",
        "appreciate",
        "congratulations"
    ]

    # -----------------------------------------------------
    # Negative keywords
    # -----------------------------------------------------

    negative_words = [

        "bad",
        "worst",
        "angry",
        "hate",
        "problem",
        "issue",
        "error",
        "complaint",
        "fraud",
        "scam",
        "danger",
        "fail",
        "failed",
        "terrible",
        "disappointed"
    ]

    # -----------------------------------------------------
    # Matching
    # -----------------------------------------------------

    spam_matches = [
        word
        for word in spam_keywords
        if word in text
    ]

    important_matches = [
        word
        for word in important_keywords
        if word in text
    ]

    positive_matches = [
        word
        for word in positive_words
        if word in text
    ]

    negative_matches = [
        word
        for word in negative_words
        if word in text
    ]

    # -----------------------------------------------------
    # Sentiment
    # -----------------------------------------------------

    if len(positive_matches) > len(negative_matches):

        sentiment = "Positive"

    elif len(negative_matches) > len(positive_matches):

        sentiment = "Negative"

    else:

        sentiment = "Neutral"

    # -----------------------------------------------------
    # Category + Risk
    # -----------------------------------------------------

    if len(spam_matches) >= 2:

        category = "Spam"

        risk_level = "High"

    elif len(spam_matches) == 1:

        category = "Spam"

        risk_level = "Medium"

    elif len(important_matches) >= 2:

        category = "Important"

        risk_level = "Low"

    elif len(important_matches) == 1:

        category = "Important"

        risk_level = "Low"

    elif len(negative_matches) >= 2:

        category = "Important"

        risk_level = "Medium"

    else:

        category = "Normal"

        risk_level = "Low"

    # -----------------------------------------------------
    # Analysis reason
    # -----------------------------------------------------

    reasons = []

    if spam_matches:

        reasons.append(
            "Spam keywords: "
            + ", ".join(spam_matches)
        )

    if important_matches:

        reasons.append(
            "Important keywords: "
            + ", ".join(important_matches)
        )

    if positive_matches:

        reasons.append(
            "Positive sentiment detected"
        )

    if negative_matches:

        reasons.append(
            "Negative sentiment detected"
        )

    if not reasons:

        reasons.append(
            "No suspicious keywords detected"
        )

    analysis_reason = " | ".join(reasons)

    return (
        category,
        risk_level,
        sentiment,
        analysis_reason
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_required():

    if not session.get(
        "admin_logged_in",
        False
    ):

        return False

    if session.get(
        "admin_role"
    ) != ADMIN_ROLE:

        return False

    return True


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# CONTACT FORM
# =========================================================

@app.route(
    "/contact",
    methods=["POST"]
)
def contact():

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if not name or not email or not message:

        flash(
            "Please fill all fields.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    if len(name) > 100:

        flash(
            "Name is too long.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    if len(email) > 150:

        flash(
            "Email is too long.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    if len(message) > 2000:

        flash(
            "Message is too long.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    # -----------------------------------------------------
    # Rate limiting
    # -----------------------------------------------------

    ip_address = request.remote_addr or "unknown"

    now = datetime.now()

    previous_requests = contact_rate_limit.get(
        ip_address,
        []
    )

    previous_requests = [

        request_time

        for request_time in previous_requests

        if (
            now - request_time
        ).total_seconds() < CONTACT_TIME_WINDOW
    ]

    if len(previous_requests) >= MAX_CONTACT_MESSAGES:

        flash(
            "Too many messages. Please try again later.",
            "error"
        )

        return redirect(
            url_for("home")
        )

    previous_requests.append(now)

    contact_rate_limit[
        ip_address
    ] = previous_requests

    # -----------------------------------------------------
    # AI analysis
    # -----------------------------------------------------

    (
        category,
        risk_level,
        sentiment,
        analysis_reason
    ) = analyze_message(message)

    # -----------------------------------------------------
    # Save message
    # -----------------------------------------------------

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO messages
        (
            name,
            email,
            message,
            created_at,
            category,
            risk_level,
            sentiment,
            analysis_reason
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        message,
        india_time(),
        category,
        risk_level,
        sentiment,
        analysis_reason
    ))

    conn.commit()

    conn.close()

    log_activity(
        f"New Contact Message - {name}"
    )

    flash(
        "Your message has been sent successfully!",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if admin_required():

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        client_ip = request.remote_addr or "unknown"

        # -------------------------------------------------
        # Lockout check
        # -------------------------------------------------

        login_info = failed_login_attempts.get(
            client_ip
        )

        if login_info:

            attempts = login_info.get(
                "attempts",
                0
            )

            locked_until = login_info.get(
                "locked_until"
            )

            if locked_until:

                if datetime.now() < locked_until:

                    log_activity(
                        "Login Blocked - Lockout"
                    )

                    flash(
                        "Too many failed attempts. Please try again later.",
                        "error"
                    )

                    return render_template(
                        "admin_login.html"
                    )

                else:

                    failed_login_attempts.pop(
                        client_ip,
                        None
                    )

        # -------------------------------------------------
        # Login validation
        # -------------------------------------------------

        if (
            username == ADMIN_USERNAME
            and
            password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True

            session["admin_username"] = (
                ADMIN_USERNAME
            )

            session["admin_role"] = (
                ADMIN_ROLE
            )

            failed_login_attempts.pop(
                client_ip,
                None
            )

            log_activity(
                "Admin Login Successful"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        # -------------------------------------------------
        # Failed login
        # -------------------------------------------------

        login_info = failed_login_attempts.get(
            client_ip,
            {
                "attempts": 0,
                "locked_until": None
            }
        )

        login_info["attempts"] += 1

        if login_info["attempts"] >= MAX_LOGIN_ATTEMPTS:

            login_info["locked_until"] = (
                datetime.now()
                + timedelta(
                    minutes=LOCKOUT_MINUTES
                )
            )

            log_activity(
                "Admin Login Failed - Account Locked"
            )

            flash(
                "Too many failed attempts. Login temporarily locked.",
                "error"
            )

        else:

            remaining = (
                MAX_LOGIN_ATTEMPTS
                - login_info["attempts"]
            )

            log_activity(
                "Admin Login Failed"
            )

            flash(
                f"Invalid login. {remaining} attempts remaining.",
                "error"
            )

        failed_login_attempts[
            client_ip
        ] = login_info

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    messages = conn.execute("""
        SELECT *

        FROM messages

        ORDER BY id DESC
    """).fetchall()

    # -----------------------------------------------------
    # Statistics
    # -----------------------------------------------------

    total = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
    """).fetchone()["count"]

    normal = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Normal'
    """).fetchone()["count"]

    important = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Important'
    """).fetchone()["count"]

    spam = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Spam'
    """).fetchone()["count"]

    high_risk = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE risk_level = 'High'
    """).fetchone()["count"]

    positive = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Positive'
    """).fetchone()["count"]

    negative = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Negative'
    """).fetchone()["count"]

    successful_logins = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE '%Login Successful%'
    """).fetchone()["count"]

    failed_logins = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE '%Login Failed%'
    """).fetchone()["count"]

    deleted_messages = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE '%Deleted%'
    """).fetchone()["count"]

    total_security_events = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
    """).fetchone()["count"]

    last_activity = conn.execute("""
        SELECT created_at

        FROM activity_logs

        ORDER BY id DESC

        LIMIT 1
    """).fetchone()

    conn.close()

    last_activity_time = (
        last_activity["created_at"]
        if last_activity
        else "No activity"
    )

    db_status = (
        "Online"
        if os.path.exists(DATABASE)
        else "Offline"
    )

    server_status = "Online"

    session_status = "Active"

    if high_risk > 0:

        overall_health = "Warning"

        security_alert = (
            f"{high_risk} high-risk message(s) detected."
        )

    else:

        overall_health = "Healthy"

        security_alert = (
            "No high-risk messages detected."
        )

    return render_template(
        "admin_dashboard.html",

        messages=messages,

        total=total,

        normal=normal,

        important=important,

        spam=spam,

        high_risk=high_risk,

        positive=positive,

        negative=negative,

        successful_logins=successful_logins,

        failed_logins=failed_logins,

        deleted_messages=deleted_messages,

        total_security_events=total_security_events,

        db_records=total,

        last_activity=last_activity_time,

        db_status=db_status,

        server_status=server_status,

        session_status=session_status,

        overall_health=overall_health,

        security_alert=security_alert
    )


# =========================================================
# ADMIN LOGS
# =========================================================

@app.route("/admin/logs")
def admin_logs():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    logs = conn.execute("""
        SELECT *

        FROM activity_logs

        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_logs.html",
        logs=logs
    )


# =========================================================
# DELETE MESSAGE
# =========================================================

@app.route(
    "/admin/delete/<int:message_id>",
    methods=["POST"]
)
def delete_message(message_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    message = conn.execute("""
        SELECT name

        FROM messages

        WHERE id = ?
    """, (
        message_id,
    )).fetchone()

    if message:

        conn.execute("""
            DELETE FROM messages

            WHERE id = ?
        """, (
            message_id,
        ))

        conn.commit()

        log_activity(
            f"Deleted Message - {message['name']}"
        )

        flash(
            "Message deleted successfully.",
            "success"
        )

    else:

        flash(
            "Message not found.",
            "error"
        )

    conn.close()

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# CSV EXPORT
# =========================================================

@app.route("/admin/export")
def export_csv():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    messages = conn.execute("""
        SELECT *

        FROM messages

        ORDER BY id DESC
    """).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Name",
        "Email",
        "Message",
        "Date & Time",
        "Category",
        "Risk Level",
        "Sentiment",
        "Analysis Reason"
    ])

    for message in messages:

        writer.writerow([
            message["id"],
            message["name"],
            message["email"],
            message["message"],
            message["created_at"],
            message["category"],
            message["risk_level"],
            message["sentiment"],
            message["analysis_reason"]
        ])

    log_activity(
        "CSV Export Generated"
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=portfolio_messages.csv"
        }
    )


# =========================================================
# DATABASE BACKUP
# =========================================================

@app.route("/admin/backup")
def backup_database():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    if not os.path.exists(DATABASE):

        flash(
            "Database file not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_filename = (
        f"portfolio_backup_{timestamp}.db"
    )

    backup_path = os.path.join(
        BACKUP_FOLDER,
        backup_filename
    )

    shutil.copy2(
        DATABASE,
        backup_path
    )

    log_activity(
        f"Database Backup Created - {backup_filename}"
    )

    return send_file(
        backup_path,
        as_attachment=True,
        download_name=backup_filename
    )


# =========================================================
# DATABASE RESTORE
# =========================================================

@app.route(
    "/admin/restore",
    methods=["POST"]
)
def restore_database():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    uploaded_file = request.files.get(
        "database_file"
    )

    if not uploaded_file:

        flash(
            "Please select a database file.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    filename = uploaded_file.filename or ""

    if not filename.lower().endswith(".db"):

        flash(
            "Only .db files are allowed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # -----------------------------------------------------
    # Safety backup
    # -----------------------------------------------------

    if os.path.exists(DATABASE):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        safety_backup = os.path.join(
            BACKUP_FOLDER,
            f"before_restore_{timestamp}.db"
        )

        shutil.copy2(
            DATABASE,
            safety_backup
        )

    # -----------------------------------------------------
    # Temporary upload
    # -----------------------------------------------------

    temp_path = os.path.join(
        BASE_DIR,
        "restore_temp.db"
    )

    uploaded_file.save(
        temp_path
    )

    # -----------------------------------------------------
    # Integrity check
    # -----------------------------------------------------

    try:

        test_conn = sqlite3.connect(
            temp_path
        )

        result = test_conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        test_conn.close()

        if result != "ok":

            os.remove(temp_path)

            flash(
                "Database integrity check failed.",
                "error"
            )

            return redirect(
                url_for("admin_dashboard")
            )

    except Exception:

        if os.path.exists(temp_path):

            os.remove(temp_path)

        flash(
            "Invalid database file.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # -----------------------------------------------------
    # Replace database
    # -----------------------------------------------------

    shutil.copy2(
        temp_path,
        DATABASE
    )

    os.remove(
        temp_path
    )

    log_activity(
        f"Database Restore Completed - {filename}"
    )

    flash(
        "Database restored successfully.",
        "success"
    )

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# PDF REPORT
# =========================================================

@app.route("/admin/report")
def generate_report():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )

    try:

        from reportlab.lib import colors

        from reportlab.lib.pagesizes import A4

        from reportlab.lib.styles import getSampleStyleSheet

        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle
        )

    except ImportError:

        flash(
            "ReportLab is not installed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    conn = get_db_connection()

    messages = conn.execute("""
        SELECT *

        FROM messages

        ORDER BY id DESC
    """).fetchall()

    total = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
    """).fetchone()["count"]

    spam = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Spam'
    """).fetchone()["count"]

    important = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Important'
    """).fetchone()["count"]

    high_risk = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE risk_level = 'High'
    """).fetchone()["count"]

    conn.close()

    filename = os.path.join(
        BASE_DIR,
        "Sakthi_Narendran_Portfolio_Report.pdf"
    )

    document = SimpleDocTemplate(
        filename,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "Sakthi Narendran - Portfolio Security Report",
            styles["Title"]
        )
    )

    story.append(
        Spacer(
            1,
            20
        )
    )

    story.append(
        Paragraph(
            f"Generated: {india_time()}",
            styles["Normal"]
        )
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    summary_data = [

        ["System Summary", "Value"],

        ["Total Messages", str(total)],

        ["Important Messages", str(important)],

        ["Spam Messages", str(spam)],

        ["High Risk Messages", str(high_risk)],

        ["Admin Security", "Enabled"],

        ["Database", "SQLite"],

        ["Server", "Flask"]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[250, 200]
    )

    summary_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.grey
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            )
        ])
    )

    story.append(
        summary_table
    )

    story.append(
        Spacer(
            1,
            20
        )
    )

    story.append(
        Paragraph(
            "AI Message Analysis",
            styles["Heading2"]
        )
    )

    story.append(
        Spacer(
            1,
            10
        )
    )

    message_data = [[
        "ID",
        "Name",
        "Category",
        "Risk",
        "Sentiment"
    ]]

    for message in messages:

        message_data.append([

            str(message["id"]),

            message["name"][:25],

            message["category"],

            message["risk_level"],

            message["sentiment"]
        ])

    message_table = Table(
        message_data,
        repeatRows=1
    )

    message_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.grey
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ])
    )

    story.append(
        message_table
    )

    story.append(
        Spacer(
            1,
            20
        )
    )

    story.append(
        Paragraph(
            "Security Protection",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            "Admin authentication, login lockout, "
            "contact rate limiting, activity logging, "
            "SQLite backup and restore, AI-style message "
            "classification and risk detection are enabled.",
            styles["Normal"]
        )
    )

    document.build(
        story
    )

    log_activity(
        "PDF Report Generated"
    )

    return send_file(
        filename,
        as_attachment=True,
        download_name="Sakthi_Narendran_Portfolio_Report.pdf"
    )


# =========================================================
# REAL-TIME NOTIFICATIONS API
# =========================================================

@app.route(
    "/admin/notifications"
)
def admin_notifications():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Unauthorized"
        }), 401

    conn = get_db_connection()

    messages = conn.execute("""
        SELECT
            id,
            name,
            email,
            message,
            category,
            risk_level,
            sentiment,
            created_at

        FROM messages

        ORDER BY id DESC

        LIMIT 10
    """).fetchall()

    conn.close()

    result = []

    for message in messages:

        result.append({

            "id": message["id"],

            "name": message["name"],

            "email": message["email"],

            "message": message["message"],

            "category": message["category"],

            "risk_level": message["risk_level"],

            "sentiment": message["sentiment"],

            "created_at": message["created_at"]
        })

    return jsonify({

        "success": True,

        "messages": result
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    if admin_required():

        log_activity(
            "Admin Logout"
        )

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <h1>404 - Page Not Found</h1>
    <p>The requested page does not exist.</p>
    """, 404


@app.errorhandler(500)
def internal_server_error(error):

    return """
    <h1>500 - Internal Server Error</h1>
    <p>Something went wrong on the server.</p>
    """, 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    create_database()

    print()
    print("=" * 55)
    print("Sakthi Narendran Personal Portfolio")
    print("=" * 55)
    print()
    print("Server:")
    print("http://127.0.0.1:5000")
    print()
    print("Admin:")
    print("http://127.0.0.1:5000/admin/login")
    print()
    print("Username:")
    print(ADMIN_USERNAME)
    print()
    print("Password:")
    print("Use ADMIN_PASSWORD environment variable")
    print()
    print("=" * 55)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )