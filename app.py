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


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = "sakthi_portfolio_secure_secret_key_2026"


# ============================================================
# DATABASE SETTINGS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "portfolio.db"
)

BACKUP_FOLDER = os.path.join(
    BASE_DIR,
    "database_backups"
)

os.makedirs(
    BACKUP_FOLDER,
    exist_ok=True
)


# ============================================================
# ADMIN SETTINGS
# ============================================================

ADMIN_USERNAME = "admin"

ADMIN_PASSWORD = "Admin@123"

ADMIN_ROLE = "Super Admin"


# ============================================================
# SECURITY SETTINGS
# ============================================================

MAX_LOGIN_ATTEMPTS = 5

LOCKOUT_MINUTES = 5

MAX_CONTACT_MESSAGES = 3

CONTACT_TIME_WINDOW = 60


failed_login_attempts = {}

contact_rate_limit = {}


# ============================================================
# TIME FUNCTION
# ============================================================

def get_india_time():

    utc_now = datetime.now(timezone.utc)

    india_time = utc_now + timedelta(hours=5, minutes=30)

    return india_time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# CREATE DATABASE
# ============================================================

def create_database():

    conn = get_db()

    cursor = conn.cursor()


    # --------------------------------------------------------
    # MESSAGES TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL,

            message TEXT NOT NULL,

pu            created_at TEXT,

            category TEXT DEFAULT 'Normal',

            risk_level TEXT DEFAULT 'Low',

            sentiment TEXT DEFAULT 'Neutral',

            analysis_reason TEXT

        )
    """)


    # --------------------------------------------------------
    # ACTIVITY LOGS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            action TEXT NOT NULL,

            created_at TEXT

        )
    """)


    # --------------------------------------------------------
    # CHECK OLD DATABASE COLUMNS
    # --------------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(messages)"
    )

    columns = [
        row["name"]
        for row in cursor.fetchall()
    ]


    if "created_at" not in columns:

        cursor.execute("""
            ALTER TABLE messages
            ADD COLUMN created_at TEXT
        """)


    if "category" not in columns:

        cursor.execute("""
            ALTER TABLE messages
            ADD COLUMN category TEXT DEFAULT 'Normal'
        """)


    if "risk_level" not in columns:

        cursor.execute("""
            ALTER TABLE messages
            ADD COLUMN risk_level TEXT DEFAULT 'Low'
        """)


    if "sentiment" not in columns:

        cursor.execute("""
            ALTER TABLE messages
            ADD COLUMN sentiment TEXT DEFAULT 'Neutral'
        """)


    if "analysis_reason" not in columns:

        cursor.execute("""
            ALTER TABLE messages
            ADD COLUMN analysis_reason TEXT
        """)


    # --------------------------------------------------------
    # UPDATE EMPTY VALUES
    # --------------------------------------------------------

    cursor.execute("""
        UPDATE messages
        SET created_at = ?
        WHERE created_at IS NULL
        OR created_at = ''
    """, (
        get_india_time(),
    ))


    cursor.execute("""
        UPDATE messages
        SET category = 'Normal'
        WHERE category IS NULL
        OR category = ''
    """)


    cursor.execute("""
        UPDATE messages
        SET risk_level = 'Low'
        WHERE risk_level IS NULL
        OR risk_level = ''
    """)


    cursor.execute("""
        UPDATE messages
        SET sentiment = 'Neutral'
        WHERE sentiment IS NULL
        OR sentiment = ''
    """)


    conn.commit()

    conn.close()


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(action):

    try:

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activity_logs
            (
                action,
                created_at
            )
            VALUES (?, ?)
        """, (
            action,
            get_india_time()
        ))

        conn.commit()

        conn.close()

    except Exception as error:

        print(
            "Activity log error:",
            error
        )


# ============================================================
# AI MESSAGE ANALYSIS
# ============================================================

def analyze_message(message):

    text = message.lower()


    # --------------------------------------------------------
    # SPAM KEYWORDS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # IMPORTANT KEYWORDS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # POSITIVE WORDS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # NEGATIVE WORDS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # SENTIMENT
    # --------------------------------------------------------

    if len(positive_matches) > len(negative_matches):

        sentiment = "Positive"

    elif len(negative_matches) > len(positive_matches):

        sentiment = "Negative"

    else:

        sentiment = "Neutral"


    # --------------------------------------------------------
    # CATEGORY & RISK
    # --------------------------------------------------------

    if len(spam_matches) >= 2:

        category = "Spam"

        risk_level = "High"

        reason = (
            "Multiple spam-related keywords detected: "
            + ", ".join(spam_matches)
        )


    elif len(spam_matches) == 1:

        category = "Spam"

        risk_level = "Medium"

        reason = (
            "Spam-related keyword detected: "
            + spam_matches[0]
        )


    elif len(important_matches) >= 2:

        category = "Important"

        risk_level = "Low"

        reason = (
            "Multiple important keywords detected: "
            + ", ".join(important_matches)
        )


    elif len(important_matches) == 1:

        category = "Important"

        risk_level = "Low"

        reason = (
            "Important keyword detected: "
            + important_matches[0]
        )


    elif len(negative_matches) >= 2:

        category = "Important"

        risk_level = "Medium"

        reason = (
            "Negative or complaint-related content detected."
        )


    else:

        category = "Normal"

        risk_level = "Low"

        reason = (
            "No major spam or high-risk pattern detected."
        )


    return (
        category,
        risk_level,
        sentiment,
        reason
    )


# ============================================================
# ADMIN LOGIN CHECK
# ============================================================

def admin_required():

    return (
        "admin_logged_in" in session
        and session.get("admin_role") == ADMIN_ROLE
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# CONTACT FORM
# ============================================================

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


    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

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


    if len(message) > 5000:

        flash(
            "Message is too long.",
            "error"
        )

        return redirect(
            url_for("home")
        )


    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    ip_address = (
        request.headers.get(
            "X-Forwarded-For"
        )
        or request.remote_addr
        or "unknown"
    )


    now = datetime.now()


    if ip_address in contact_rate_limit:

        timestamps = contact_rate_limit[
            ip_address
        ]

        timestamps = [

            timestamp
            for timestamp in timestamps

            if (
                now - timestamp
            ).total_seconds()
            < CONTACT_TIME_WINDOW

        ]


        if len(timestamps) >= MAX_CONTACT_MESSAGES:

            flash(
                "Too many messages. Please try again later.",
                "error"
            )

            return redirect(
                url_for("home")
            )


        timestamps.append(now)

        contact_rate_limit[
            ip_address
        ] = timestamps


    else:

        contact_rate_limit[
            ip_address
        ] = [now]


    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    (
        category,
        risk_level,
        sentiment,
        analysis_reason
    ) = analyze_message(
        message
    )


    # --------------------------------------------------------
    # SAVE MESSAGE
    # --------------------------------------------------------

    conn = get_db()

    cursor = conn.cursor()


    cursor.execute("""
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
        get_india_time(),
        category,
        risk_level,
        sentiment,
        analysis_reason

    ))


    message_id = cursor.lastrowid


    conn.commit()

    conn.close()


    flash(
        "Message sent successfully!",
        "success"
    )


    print(
        "New message:",
        message_id,
        category,
        risk_level
    )


    return redirect(
        url_for("home")
    )


# ============================================================
# ADMIN LOGIN PAGE
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "GET":

        return render_template(
            "admin_login.html"
        )


    username = request.form.get(
        "username",
        ""
    ).strip()


    password = request.form.get(
        "password",
        ""
    )


    ip_address = (
        request.remote_addr
        or "unknown"
    )


    # --------------------------------------------------------
    # CHECK LOCKOUT
    # --------------------------------------------------------

    if ip_address in failed_login_attempts:

        data = failed_login_attempts[
            ip_address
        ]


        if data.get("locked_until"):

            if datetime.now() < data["locked_until"]:

                remaining = (
                    data["locked_until"]
                    - datetime.now()
                ).seconds // 60 + 1


                log_activity(
                    "Admin Login Failed - Account Locked"
                )


                return render_template(
                    "admin_login.html",
                    error=(
                        "Account temporarily locked. "
                        f"Try again in {remaining} minute(s)."
                    )
                )


            else:

                failed_login_attempts[
                    ip_address
                ] = {
                    "attempts": 0,
                    "locked_until": None
                }


    # --------------------------------------------------------
    # VERIFY LOGIN
    # --------------------------------------------------------

    valid_username = (
        username == ADMIN_USERNAME
    )


    valid_password = check_password_hash(
        generate_password_hash(
            ADMIN_PASSWORD
        ),
        password
    )


    if valid_username and valid_password:

        session.clear()

        session["admin_logged_in"] = True

        session["admin_username"] = (
            ADMIN_USERNAME
        )

        session["admin_role"] = (
            ADMIN_ROLE
        )


        failed_login_attempts.pop(
            ip_address,
            None
        )


        log_activity(
            "Admin Login Successful"
        )


        return redirect(
            url_for("admin_dashboard")
        )


    # --------------------------------------------------------
    # FAILED LOGIN
    # --------------------------------------------------------

    if ip_address not in failed_login_attempts:

        failed_login_attempts[
            ip_address
        ] = {

            "attempts": 0,

            "locked_until": None

        }


    failed_login_attempts[
        ip_address
    ]["attempts"] += 1


    attempts = failed_login_attempts[
        ip_address
    ]["attempts"]


    if attempts >= MAX_LOGIN_ATTEMPTS:

        failed_login_attempts[
            ip_address
        ]["locked_until"] = (
            datetime.now()
            + timedelta(
                minutes=LOCKOUT_MINUTES
            )
        )


        log_activity(
            "Admin Login Failed - Account Locked"
        )


        return render_template(
            "admin_login.html",
            error=(
                "Too many failed attempts. "
                "Account locked for 5 minutes."
            )
        )


    log_activity(
        "Admin Login Failed"
    )


    remaining_attempts = (
        MAX_LOGIN_ATTEMPTS
        - attempts
    )


    return render_template(
        "admin_login.html",
        error=(
            "Invalid username or password. "
            f"{remaining_attempts} attempt(s) remaining."
        )
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()

    cursor = conn.cursor()


    # --------------------------------------------------------
    # TOTAL MESSAGES
    # --------------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) AS count FROM messages"
    )

    total = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # AI STATISTICS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Normal'
    """)

    normal_messages = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Important'
    """)

    important_messages = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Spam'
    """)

    spam_messages = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE risk_level = 'High'
    """)

    high_risk_messages = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Positive'
    """)

    positive_messages = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Negative'
    """)

    negative_messages = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # LOGIN STATISTICS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action = 'Admin Login Successful'
    """)

    successful_logins = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE 'Admin Login Failed%'
    """)

    failed_logins = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # DELETE STATISTICS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE 'Message Deleted%'
    """)

    deleted_messages = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # SECURITY EVENTS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
    """)

    total_security_events = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # DATABASE RECORDS
    # --------------------------------------------------------

    database_records = (
        total
        + total_security_events
    )


    # --------------------------------------------------------
    # LAST ACTIVITY
    # --------------------------------------------------------

    cursor.execute("""
        SELECT created_at
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 1
    """)

    last_activity_row = cursor.fetchone()


    if last_activity_row:

        last_activity = (
            last_activity_row["created_at"]
        )

    else:

        last_activity = "No activity"


    # --------------------------------------------------------
    # GET MESSAGES
    # --------------------------------------------------------

    cursor.execute("""
        SELECT *
        FROM messages
        ORDER BY id DESC
    """)

    messages = cursor.fetchall()


    conn.close()


    # --------------------------------------------------------
    # DATABASE HEALTH
    # --------------------------------------------------------

    database_status = "Connected"

    overall_health = "Healthy"

    overall_health_type = "healthy"


    try:

        test_conn = get_db()

        test_conn.execute(
            "SELECT 1"
        )

        test_conn.close()

    except Exception:

        database_status = "Error"

        overall_health = "Attention Required"

        overall_health_type = "warning"


    # --------------------------------------------------------
    # SECURITY ALERT
    # --------------------------------------------------------

    if high_risk_messages > 0:

        security_alert = (
            f"High-risk messages detected: "
            f"{high_risk_messages}"
        )

        security_alert_type = "critical"


    elif spam_messages > 0:

        security_alert = (
            f"Spam messages detected: "
            f"{spam_messages}"
        )

        security_alert_type = "warning"


    else:

        security_alert = (
            "All security systems are operating normally."
        )

        security_alert_type = "safe"


    return render_template(

        "admin_dashboard.html",

        messages=messages,

        total=total,

        normal_messages=normal_messages,

        important_messages=important_messages,

        spam_messages=spam_messages,

        high_risk_messages=high_risk_messages,

        positive_messages=positive_messages,

        negative_messages=negative_messages,

        successful_logins=successful_logins,

        failed_logins=failed_logins,

        deleted_messages=deleted_messages,

        total_security_events=total_security_events,

        database_records=database_records,

        last_activity=last_activity,

        database_status=database_status,

        server_status="Online",

        admin_session_status="Active",

        overall_health=overall_health,

        overall_health_type=overall_health_type,

        security_alert=security_alert,

        security_alert_type=security_alert_type

    )


# ============================================================
# REAL-TIME NOTIFICATION API
# ============================================================

@app.route("/admin/notifications")
def admin_notifications():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Unauthorized"
        }), 401


    try:

        conn = get_db()

        cursor = conn.cursor()


        cursor.execute("""
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
        """)


        rows = cursor.fetchall()

        conn.close()


        result = []


        for row in rows:

            result.append({

                "id": row["id"],

                "name": row["name"],

                "email": row["email"],

                "message": row["message"],

                "category": row["category"],

                "risk_level": row["risk_level"],

                "sentiment": row["sentiment"],

                "created_at": row["created_at"]

            })


        return jsonify({

            "success": True,

            "messages": result

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "message": str(error)

        }), 500


# ============================================================
# ADMIN LOGS
# ============================================================

@app.route("/admin/logs")
def admin_logs():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
    """)


    logs = cursor.fetchall()


    conn.close()


    return render_template(
        "admin_logs.html",
        logs=logs
    )


# ============================================================
# DELETE MESSAGE
# ============================================================

@app.route(
    "/admin/delete/<int:message_id>"
)
def delete_message(message_id):

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute("""
        DELETE FROM messages
        WHERE id = ?
    """, (
        message_id,
    ))


    conn.commit()

    conn.close()


    log_activity(
        f"Message Deleted - ID {message_id}"
    )


    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# CSV EXPORT
# ============================================================

@app.route("/admin/export")
def export_csv():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute("""
        SELECT
            id,
            name,
            email,
            message,
            created_at,
            category,
            risk_level,
            sentiment,
            analysis_reason
        FROM messages
        ORDER BY id DESC
    """)


    rows = cursor.fetchall()

    conn.close()


    output = io.StringIO()

    writer = csv.writer(
        output
    )


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


    for row in rows:

        writer.writerow([

            row["id"],
            row["name"],
            row["email"],
            row["message"],
            row["created_at"],
            row["category"],
            row["risk_level"],
            row["sentiment"],
            row["analysis_reason"]

        ])


    log_activity(
        "Contact Messages CSV Exported"
    )


    return Response(

        output.getvalue(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
            "attachment; filename=portfolio_messages.csv"

        }

    )


# ============================================================
# DATABASE BACKUP
# ============================================================

@app.route("/admin/backup")
def backup_database():

    if not admin_required():

        return redirect(
            url_for("admin_login")
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


    try:

        shutil.copy2(

            DATABASE,

            backup_path

        )


        log_activity(
            "Database Backup Created - "
            + backup_filename
        )


        return send_file(

            backup_path,

            as_attachment=True,

            download_name=backup_filename

        )


    except Exception as error:

        flash(
            f"Backup failed: {error}",
            "error"
        )


        return redirect(
            url_for("admin_dashboard")
        )


# ============================================================
# DATABASE RESTORE
# ============================================================

@app.route(
    "/admin/restore",
    methods=["POST"]
)
def restore_database():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    backup_file = request.files.get(
        "backup_file"
    )


    if not backup_file:

        flash(
            "Please select a database backup file.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )


    filename = backup_file.filename or ""


    if not filename.lower().endswith(".db"):

        flash(
            "Only .db files are allowed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    safety_backup = os.path.join(

        BACKUP_FOLDER,

        f"before_restore_{timestamp}.db"

    )


    temporary_restore = os.path.join(

        BACKUP_FOLDER,

        f"restore_temp_{timestamp}.db"

    )


    try:

        # ----------------------------------------------------
        # CREATE SAFETY BACKUP
        # ----------------------------------------------------

        shutil.copy2(

            DATABASE,

            safety_backup

        )


        # ----------------------------------------------------
        # SAVE UPLOADED FILE TEMPORARILY
        # ----------------------------------------------------

        backup_file.save(
            temporary_restore
        )


        # ----------------------------------------------------
        # VERIFY SQLITE DATABASE
        # ----------------------------------------------------

        test_conn = sqlite3.connect(
            temporary_restore
        )


        test_conn.execute(
            "PRAGMA integrity_check"
        )


        test_conn.close()


        # ----------------------------------------------------
        # REPLACE DATABASE
        # ----------------------------------------------------

        shutil.copy2(

            temporary_restore,

            DATABASE

        )


        # ----------------------------------------------------
        # REMOVE TEMP FILE
        # ----------------------------------------------------

        os.remove(
            temporary_restore
        )


        log_activity(
            "Database Restored - "
            + filename
        )


        flash(
            "Database restored successfully.",
            "success"
        )


    except Exception as error:

        if os.path.exists(
            temporary_restore
        ):

            os.remove(
                temporary_restore
            )


        flash(
            f"Database restore failed: {error}",
            "error"
        )


    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# PDF REPORT
# ============================================================

@app.route("/admin/report")
def generate_report():

    if not admin_required():

        return redirect(
            url_for("admin_login")
        )


    try:

        from reportlab.lib import colors

        from reportlab.lib.pagesizes import A4

        from reportlab.lib.styles import (
            getSampleStyleSheet
        )

        from reportlab.lib.units import mm

        from reportlab.platypus import (

            SimpleDocTemplate,

            Paragraph,

            Spacer,

            Table,

            TableStyle

        )


    except ImportError:

        flash(
            "ReportLab is not installed. Run: pip install reportlab",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )


    conn = get_db()

    cursor = conn.cursor()


    # --------------------------------------------------------
    # MESSAGE STATISTICS
    # --------------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) AS count FROM messages"
    )

    total = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Normal'
    """)

    normal = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Important'
    """)

    important = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE category = 'Spam'
    """)

    spam = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE risk_level = 'High'
    """)

    high_risk = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Positive'
    """)

    positive = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE sentiment = 'Negative'
    """)

    negative = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # SECURITY STATISTICS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action = 'Admin Login Successful'
    """)

    successful_logins = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE 'Admin Login Failed%'
    """)

    failed_logins = cursor.fetchone()["count"]


    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action LIKE 'Message Deleted%'
    """)

    deleted_messages = cursor.fetchone()["count"]


    # --------------------------------------------------------
    # MESSAGE DATA
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            name,
            email,
            category,
            risk_level,
            sentiment,
            created_at
        FROM messages
        ORDER BY id DESC
    """)


    messages = cursor.fetchall()


    conn.close()


    # --------------------------------------------------------
    # PDF FILE
    # --------------------------------------------------------

    pdf_buffer = io.BytesIO()


    doc = SimpleDocTemplate(

        pdf_buffer,

        pagesize=A4,

        rightMargin=15 * mm,

        leftMargin=15 * mm,

        topMargin=15 * mm,

        bottomMargin=15 * mm

    )


    styles = getSampleStyleSheet()


    story = []


    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "Sakthi Narendran - Portfolio Admin Report",
            styles["Title"]
        )

    )


    story.append(
        Spacer(1, 8)
    )


    story.append(

        Paragraph(

            "Generated: "
            + get_india_time(),

            styles["Normal"]

        )

    )


    story.append(
        Spacer(1, 15)
    )


    # --------------------------------------------------------
    # SYSTEM SUMMARY
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "System Summary",
            styles["Heading2"]
        )

    )


    summary_data = [

        ["Total Messages", str(total)],

        ["Normal Messages", str(normal)],

        ["Important Messages", str(important)],

        ["Spam Messages", str(spam)],

        ["High Risk Messages", str(high_risk)],

        ["Positive Messages", str(positive)],

        ["Negative Messages", str(negative)],

        ["Successful Logins", str(successful_logins)],

        ["Failed Logins", str(failed_logins)],

        ["Deleted Messages", str(deleted_messages)],

    ]


    summary_table = Table(
        summary_data,
        colWidths=[
            90 * mm,
            70 * mm
        ]
    )


    summary_table.setStyle(

        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.lightgrey
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
        Spacer(1, 15)
    )


    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "AI Message Analysis",
            styles["Heading2"]
        )

    )


    story.append(

        Paragraph(

            "The system performs rule-based "
            "message classification using spam, "
            "important, sentiment and risk patterns.",

            styles["Normal"]

        )

    )


    story.append(
        Spacer(1, 10)
    )


    # --------------------------------------------------------
    # MESSAGE TABLE
    # --------------------------------------------------------

    message_data = [

        [
            "ID",
            "Name",
            "Email",
            "Category",
            "Risk",
            "Sentiment"
        ]

    ]


    for message in messages:

        message_data.append([

            str(message["id"]),

            str(message["name"])[:18],

            str(message["email"])[:25],

            str(message["category"]),

            str(message["risk_level"]),

            str(message["sentiment"])

        ])


    if len(message_data) > 1:

        message_table = Table(

            message_data,

            repeatRows=1,

            colWidths=[

                12 * mm,

                30 * mm,

                50 * mm,

                30 * mm,

                25 * mm,

                30 * mm

            ]

        )


        message_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#111827")
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
                ),

            ])

        )


        story.append(
            message_table
        )


    else:

        story.append(

            Paragraph(
                "No contact messages available.",
                styles["Normal"]
            )

        )


    story.append(
        Spacer(1, 20)
    )


    # --------------------------------------------------------
    # SECURITY FEATURES
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "Security Protection",
            styles["Heading2"]
        )

    )


    security_text = """

    Login protection, brute-force protection,
    account lockout, password hashing,
    contact-message rate limiting,
    AI message analysis, activity logging,
    SQLite database backup and recovery,
    CSV export and admin access control
    are implemented in the system.

    """


    story.append(

        Paragraph(
            security_text,
            styles["Normal"]
        )

    )


    # --------------------------------------------------------
    # BUILD PDF
    # --------------------------------------------------------

    doc.build(
        story
    )


    pdf_buffer.seek(0)


    log_activity(
        "PDF Report Generated"
    )


    return send_file(

        pdf_buffer,

        as_attachment=True,

        download_name=(
            "Sakthi_Narendran_Portfolio_Report.pdf"
        ),

        mimetype="application/pdf"

    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    if "admin_logged_in" in session:

        log_activity(
            "Admin Logout"
        )


    session.clear()


    return redirect(
        url_for("admin_login")
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return """

    <h1>404 - Page Not Found</h1>

    <p>The requested page does not exist.</p>

    <a href="/">Back to Portfolio</a>

    """, 404


@app.errorhandler(500)
def internal_error(error):

    return """

    <h1>500 - Internal Server Error</h1>

    <p>Something went wrong.</p>

    <a href="/">Back to Portfolio</a>

    """, 500


# ============================================================
# CREATE DATABASE
# ============================================================

create_database()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    print(
        "\n========================================"
    )

    print(
        " Sakthi Narendran Portfolio System"
    )

    print(
        "========================================"
    )

    print(
        "Server: http://127.0.0.1:5000"
    )

    print(
        "Admin:  http://127.0.0.1:5000/admin/login"
    )

    print(
        "Username: admin"
    )

    print(
        "Password: Admin@123"
    )

    print(
        "========================================\n"
    )


    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True

    )