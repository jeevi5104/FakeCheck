from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import tempfile
import uuid
import logging

from PIL import Image
import pytesseract
import speech_recognition as sr


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=BASE_DIR)

app.secret_key = "fakecheck-secret-key"

DATABASE = os.path.join(BASE_DIR, "fakecheck.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
AUDIO_UPLOAD_FOLDER = os.path.join(BASE_DIR, "audio_uploads")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_AUDIO_EXTENSIONS = {"wav"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_UPLOAD_FOLDER, exist_ok=True)

# Tesseract configuration for Windows and Linux

if os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
else:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

logging.basicConfig(level=logging.INFO)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    conn = get_db()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                explanation TEXT NOT NULL
            )
        """)

        conn.commit()

    finally:
        conn.close()


# ============================================================
# FILE VALIDATION
# ============================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def allowed_audio_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_AUDIO_EXTENSIONS
    )


# ============================================================
# CLAIM VERIFICATION
# DEMO KNOWLEDGE BASE ONLY
# ============================================================

def check_claim(claim):

    lower_claim = claim.lower()

    false_words = [
        "earth is flat",
        "5g causes cancer",
        "water cures cancer",
        "vaccines contain microchips"
    ]

    true_words = [
        "earth revolves around the sun",
        "water freezes at 0",
        "humans need oxygen",
        "humans need oxygen to survive"
    ]

    verdict = "INSUFFICIENT EVIDENCE"
    confidence = 60

    explanation = (
        "The demo knowledge base does not contain enough "
        "information to verify this claim. Please check "
        "reliable sources before deciding whether it is true."
    )

    for word in false_words:
        if word in lower_claim:
            verdict = "REFUTED"
            confidence = 92

            explanation = (
                "This claim conflicts with established "
                "scientific knowledge. This is a demo result "
                "and should be checked against reliable sources."
            )
            break

    for word in true_words:
        if word in lower_claim:
            verdict = "SUPPORTED"
            confidence = 95

            explanation = (
                "This claim matches information in the demo "
                "knowledge base. This is not a substitute "
                "for checking reliable scientific sources."
            )
            break

    return verdict, confidence, explanation


# ============================================================
# EVIDENCE
# ============================================================

def get_evidence():

    return [
        {
            "title": "Scientific Reference",
            "description": (
                "Check reliable scientific publications "
                "and established reference sources."
            ),
            "type": "Reference"
        },
        {
            "title": "Trusted Information Source",
            "description": (
                "Compare the claim with trustworthy sources "
                "before drawing a conclusion."
            ),
            "type": "Evidence"
        }
    ]


# ============================================================
# SAVE VERIFICATION HISTORY
# ============================================================

def save_history(user, claim, verdict, confidence, explanation):

    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO verification_history
            (user, claim, verdict, confidence, explanation)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user, claim, verdict, confidence, explanation)
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            return render_template(
                "login.html",
                error="Please enter email and password."
            )

        # Demo login only; no password verification.
        session["user"] = email

        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            return render_template(
                "register.html",
                error="Please fill all fields."
            )

        # Demo registration only.
        session["user"] = email

        return redirect(url_for("dashboard"))

    return render_template("register.html")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        total = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ?
            """,
            (session["user"],)
        ).fetchone()[0]

        supported = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ? AND verdict = 'SUPPORTED'
            """,
            (session["user"],)
        ).fetchone()[0]

        refuted = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ? AND verdict = 'REFUTED'
            """,
            (session["user"],)
        ).fetchone()[0]

        insufficient = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ? AND verdict = 'INSUFFICIENT EVIDENCE'
            """,
            (session["user"],)
        ).fetchone()[0]

        recent_rows = conn.execute(
            """
            SELECT * FROM verification_history
            WHERE user = ?
            ORDER BY id DESC
            LIMIT 5
            """,
            (session["user"],)
        ).fetchall()

    finally:
        conn.close()

    recent_history = [
        {
            "claim": row["claim"],
            "verdict": row["verdict"],
            "confidence": row["confidence"],
            "explanation": row["explanation"]
        }
        for row in recent_rows
    ]

    return render_template(
        "dashboard.html",
        user=session["user"],
        total=total,
        supported=supported,
        refuted=refuted,
        insufficient=insufficient,
        recent_history=recent_history
    )


# ============================================================
# TEXT VERIFICATION PAGE
# ============================================================

@app.route("/verify-text")
def verify_text():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "verify_text.html",
        user=session["user"]
    )


# ============================================================
# VERIFY TEXT
# ============================================================

@app.route("/verify", methods=["POST"])
def verify():

    if "user" not in session:
        return redirect(url_for("login"))

    claim = request.form.get("claim", "").strip()

    if not claim:
        return render_template(
            "verify_text.html",
            user=session["user"],
            error="Please enter a claim."
        )

    verdict, confidence, explanation = check_claim(claim)
    evidence = get_evidence()

    save_history(
        session["user"],
        claim,
        verdict,
        confidence,
        explanation
    )

    return render_template(
        "verify_text.html",
        user=session["user"],
        claim=claim,
        verdict=verdict,
        confidence=confidence,
        explanation=explanation,
        evidence=evidence
    )


# ============================================================
# IMAGE VERIFICATION PAGE
# ============================================================

@app.route("/verify-image", methods=["GET"])
def verify_image():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "verify_image.html",
        user=session["user"]
    )


# ============================================================
# ============================================================
# VERIFY IMAGE
# ============================================================

@app.route("/verify-image", methods=["POST"])
def verify_image_upload():

    if "user" not in session:
        return redirect(url_for("login"))

    image_file = request.files.get("image")

    if not image_file or not image_file.filename:
        return render_template(
            "verify_image.html",
            user=session["user"],
            error="Please select an image."
        )

    if not allowed_file(image_file.filename):
        return render_template(
            "verify_image.html",
            user=session["user"],
            error="Please upload PNG, JPG, JPEG or WEBP."
        )

    image_path = None

    try:
        # Save uploaded image temporarily
        fd, image_path = tempfile.mkstemp(
            suffix=".img",
            dir=UPLOAD_FOLDER
        )
        os.close(fd)

        image_file.save(image_path)

        # Open and validate the image
        with Image.open(image_path) as original_image:

            # Check image dimensions before processing
            original_image.verify()

        with Image.open(image_path) as original_image:

            # Convert to RGB or grayscale to reduce processing overhead
            image = original_image.convert("L")

            # Resize large images to a maximum dimension of 1200 px
            max_dimension = 1200

            if max(image.size) > max_dimension:
                image.thumbnail(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS
                )

            # Limit OCR execution time to prevent long-running processing
            extracted_text = pytesseract.image_to_string(
                image,
                timeout=15,
                config="--psm 6"
            ).strip()

        # Check if OCR found readable text
        if not extracted_text:
            return render_template(
                "verify_image.html",
                user=session["user"],
                error=(
                    "No readable text found. "
                    "Please upload a clear image containing text."
                )
            )

        # Verify extracted text
        verdict, confidence, explanation = check_claim(
            extracted_text
        )

        evidence = get_evidence()

        # Save verification history
        save_history(
            session["user"],
            "[IMAGE] " + extracted_text,
            verdict,
            confidence,
            explanation
        )

        return render_template(
            "verify_image.html",
            user=session["user"],
            extracted_text=extracted_text,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence
        )

    except pytesseract.TesseractNotFoundError:
        app.logger.exception("Tesseract OCR executable not found")

        return render_template(
            "verify_image.html",
            user=session["user"],
            error=(
                "OCR service is unavailable. "
                "Please try again later."
            )
        )

    except RuntimeError:
        app.logger.exception("Image OCR timed out or failed")

        return render_template(
            "verify_image.html",
            user=session["user"],
            error=(
                "Image processing took too long. "
                "Please upload a smaller, clearer image."
            )
        )

    except Exception:
        app.logger.exception("Image verification failed")

        return render_template(
            "verify_image.html",
            user=session["user"],
            error=(
                "Unable to process this image. "
                "Please try another PNG, JPG, JPEG or WEBP image."
            )
        )

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                app.logger.warning(
                    "Unable to remove temporary image."
                )


# ============================================================
# AUDIO VERIFICATION PAGE AND PROCESSING
# ============================================================

@app.route("/verify-audio", methods=["GET", "POST"])
def verify_audio():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "verify_audio.html",
            user=session["user"]
        )

    audio_file = request.files.get("audio")

    if not audio_file or not audio_file.filename:
        return render_template(
            "verify_audio.html",
            user=session["user"],
            error="Please select an audio file."
        )

    if not allowed_audio_file(audio_file.filename):
        return render_template(
            "verify_audio.html",
            user=session["user"],
            error="Please upload a WAV audio file."
        )

    audio_path = None

    try:
        # Save uploaded audio using a unique temporary filename.
        fd, audio_path = tempfile.mkstemp(
            suffix=".wav",
            dir=AUDIO_UPLOAD_FOLDER
        )
        os.close(fd)

        audio_file.save(audio_path)

        app.logger.info("Audio upload received: %s", audio_file.filename)

        recognizer = sr.Recognizer()

        # Load the complete audio recording.
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        app.logger.info(
            "Audio loaded. Duration: %.2f seconds",
            len(audio_data.frame_data) /
            (audio_data.sample_rate * audio_data.sample_width)
        )

        # Speech recognition requires internet for recognize_google.
        app.logger.info("Starting English speech recognition.")

        extracted_text = recognizer.recognize_google(
            audio_data,
            language="en-US"
        ).strip()

        app.logger.info(
            "Recognized text: %s",
            extracted_text
        )

        if not extracted_text:
            return render_template(
                "verify_audio.html",
                user=session["user"],
                error=(
                    "No speech was detected. "
                    "Please upload a recording containing clear speech."
                )
            )

        # Run the demo claim checker.
        verdict, confidence, explanation = check_claim(
            extracted_text
        )

        evidence = get_evidence()

        # Store result in history.
        save_history(
            session["user"],
            "[AUDIO] " + extracted_text,
            verdict,
            confidence,
            explanation
        )

        # Show the result on the page.
        return render_template(
            "verify_audio.html",
            user=session["user"],
            extracted_text=extracted_text,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence
        )

    except sr.UnknownValueError:
        app.logger.warning(
            "Speech recognition could not understand the audio."
        )

        return render_template(
            "verify_audio.html",
            user=session["user"],
            error=(
                "Speech could not be understood. "
                "Please use a clear English WAV recording, "
                "speak slowly, and reduce background noise."
            )
        )

    except sr.RequestError as e:
        app.logger.exception("Speech recognition service failed.")

        return render_template(
            "verify_audio.html",
            user=session["user"],
            error=(
                "Speech recognition service failed. "
                "Check your internet connection and try again."
            ),
            details=str(e)
        )

    except Exception:
        app.logger.exception("Audio verification failed.")

        return render_template(
            "verify_audio.html",
            user=session["user"],
            error=(
                "Unable to process this audio file. "
                "Please check that it is a valid WAV recording."
            )
        )

    finally:
        # Remove temporary audio after processing.
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                app.logger.warning(
                    "Unable to remove temporary audio file."
                )


# ============================================================
# HISTORY PAGE
# ============================================================

@app.route("/history")
def history():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT * FROM verification_history
            WHERE user = ?
            ORDER BY id DESC
            """,
            (session["user"],)
        ).fetchall()

    finally:
        conn.close()

    history_data = [
        {
            "claim": row["claim"],
            "verdict": row["verdict"],
            "confidence": row["confidence"],
            "explanation": row["explanation"]
        }
        for row in rows
    ]

    return render_template(
        "history.html",
        user=session["user"],
        history=history_data
    )


# ============================================================
# EVIDENCE PAGE
# ============================================================

@app.route("/evidence")
def evidence():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        rows = conn.execute(
            """
            SELECT * FROM verification_history
            WHERE user = ?
            ORDER BY id DESC
            """,
            (session["user"],)
        ).fetchall()

    finally:
        conn.close()

    history_data = [
        {
            "claim": row["claim"],
            "verdict": row["verdict"],
            "confidence": row["confidence"],
            "explanation": row["explanation"]
        }
        for row in rows
    ]

    return render_template(
        "evidence.html",
        user=session["user"],
        history=history_data
    )


# ============================================================
# PROFILE PAGE
# ============================================================

@app.route("/profile")
def profile():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        total = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ?
            """,
            (session["user"],)
        ).fetchone()[0]

        supported = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ? AND verdict = 'SUPPORTED'
            """,
            (session["user"],)
        ).fetchone()[0]

        refuted = conn.execute(
            """
            SELECT COUNT(*) FROM verification_history
            WHERE user = ? AND verdict = 'REFUTED'
            """,
            (session["user"],)
        ).fetchone()[0]

    finally:
        conn.close()

    return render_template(
        "profile.html",
        user=session["user"],
        total=total,
        supported=supported,
        refuted=refuted
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def file_too_large(error):
    return "File is too large. Maximum size is 15 MB.", 413


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
