import os
from flask import Blueprint, request, jsonify, render_template
import cv2

from utils.segmentation import segment_image
from utils.classification import classify_disease
from utils.report_generator import generate_report

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

# -------------------------------
# GLOBAL MODELS
# -------------------------------
unet_model = None
classifier_model = None


# -------------------------------
# LOAD MODELS (FIXED PATH)
# -------------------------------
def load_models():
    global unet_model, classifier_model

    if unet_model is None or classifier_model is None:
        from tensorflow.keras.models import load_model

        print(" Loading models...")

        try:
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))

            #  Correct path for Render
            UNET_PATH = os.path.join(BASE_DIR, "..", "app", "model", "unet_model.h5")
            CLASSIFIER_PATH = os.path.join(BASE_DIR, "..", "app", "model", "classifier_model.h5")

            print("UNET PATH:", UNET_PATH)
            print("CLASSIFIER PATH:", CLASSIFIER_PATH)

            print("UNET exists:", os.path.exists(UNET_PATH))
            print("CLASSIFIER exists:", os.path.exists(CLASSIFIER_PATH))

            unet_model = load_model(UNET_PATH, compile=False)
            classifier_model = load_model(CLASSIFIER_PATH, compile=False)

            print(" Models loaded successfully")

        except Exception as e:
            print("Model loading failed:", str(e))


# -------------------------------
# CREATE FOLDERS
# -------------------------------
os.makedirs('app/static/uploaded_images', exist_ok=True)
os.makedirs('app/static/output_images', exist_ok=True)


# -------------------------------
# BLUEPRINT
# -------------------------------
main = Blueprint('main', __name__)


# -------------------------------
# HOME ROUTE
# -------------------------------
@main.route('/')
def index():
    return render_template('index.html')


# -------------------------------
# ANALYZE ROUTE
# -------------------------------
@main.route('/analyze', methods=['POST'])
def analyze():
    global unet_model, classifier_model

    try:
        #  Ensure models loaded
        if unet_model is None or classifier_model is None:
            print(" Models not loaded, loading now...")
            load_models()

        file = request.files['xray']
        name = request.form['name']
        age = float(request.form['age'])
        gender = request.form['gender']

        upload_dir = 'app/static/uploaded_images'
        output_dir = 'app/static/output_images'

        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        xray_path = os.path.join(upload_dir, file.filename)
        mask_path = os.path.join(output_dir, f'mask_{file.filename}')
        report_path = os.path.join(output_dir, f'report_{os.path.splitext(file.filename)[0]}.pdf')

        file.save(xray_path)
        

        print(" Image saved")

        #  STEP 1: Segmentation
        mask = segment_image(xray_path, unet_model)
        cv2.imwrite(mask_path, mask)

        print(" Segmentation done")

        #  STEP 2: Classification
        disease, confidence, severity = classify_disease(xray_path, classifier_model)

        print(" Classification done")

        #  STEP 3: Report
        generate_report(name, age, gender, xray_path, mask_path, disease, severity, report_path)

        print(" Report generated")
        # -----------------------
        # COMMENTS
        # -----------------------
        if severity.lower() == "low":
            comment = "Mild condition detected. No immediate risk, but monitoring is advised."
        elif severity.lower() == "medium":
            comment = "Moderate infection detected. Please consult a doctor."
        else:
            comment = "Severe condition detected. Immediate medical attention required."

        return jsonify({
            "success": True,
            "disease": disease,
            "severity": severity,
            "confidence": f"{confidence:.2f}",
            "comment": comment,
            "segmented_image": f"mask_{file.filename}",
            "pdf_report": f"report_{os.path.splitext(file.filename)[0]}.pdf"
        })

    except Exception as e:
        print(" ERROR in /analyze:", str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


