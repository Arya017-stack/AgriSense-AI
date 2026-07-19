from flask import Flask ,request, jsonify
from flask_cors import CORS 
import os
import easyocr
from werkzeug.utils import secure_filename 
from database.db import (
        create_table,
        save_receipt,
        get_all_receipts,
        get_dashboard_summary
    )
import re
import requests

reader = None

def get_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'], gpu=False)
    return reader

app =Flask(__name__)
CORS(app)
create_table()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] =UPLOAD_FOLDER

@app.route("/")

def home():
        return{
            "message":"AgriSense AI Backend Running 🚀"
        }


def generate_ai_alerts(text, crop, amount):

        alerts = []

        text = text.lower()

        if crop != "Unknown":
            alerts.append({
                "type": "success",
                "title": "Crop Detected 🌾",
                "message": f"{crop} detected from receipt."
    })

        # Pending Payment
        pending_keywords = ["pending", "due", "balance", "remaining"]

        if any(word in text for word in pending_keywords):
            alerts.append({
                "type": "warning",
                "title": "Pending Payment 💰",
                "message": "This receipt indicates a pending payment."
            })

        # Payment Completed
        paid_keywords = ["paid", "received", "completed", "success"]

        if any(word in text for word in paid_keywords):
            alerts.append({
                "type": "success",
                "title": "Payment Completed ✅",
                "message": "Payment appears to be completed."
            })

        # High Expense Detection
        try: 
            clean_amount = (
                amount.replace("KES", "")
                    .replace("₹", "")
                    .replace("Rs.", "")
                    .replace("INR", "")
                    .replace(",", "")
                    .strip()
                    
            )
            value = float(clean_amount)

            if value>30000:
                alerts.append({
                    "type":"warning",
                    "title":"High Transaction 💸",
                    "message" :f"Large amount detected :{amount}"

                })
        except Exception as e:
            print("High Transaction Detection Error:", e)
        # Low OCR Confidence (simple heuristic)
        if len(text.strip()) < 20:
            alerts.append({
                "type": "danger",
                "title": "Low OCR Confidence 🤖",
                "message": "Very little text was extracted."
            })

        # No alerts
        if len(alerts) == 0:
            alerts.append({
                "type": "info",
                "title": "Receipt Processed 📄",
                "message": "No unusual patterns detected."
            })

        return alerts

def generate_ai_confidence(crop, amount, payment_mode, date, text, ocr_confidence):

    score = 0

    if crop != "Unknown":
        score += 15
    if amount != "Not Found":
        score += 15
    if payment_mode != "Not Found":
        score += 10
    if date != "Not Found":
        score += 10

    score += (ocr_confidence * 0.5)

    missing = sum([
        crop == "Unknown",
        amount == "Not Found",
        payment_mode == "Not Found",
        date == "Not Found"
    ])
    score -= missing * 8

    score = max(0, min(round(score), 98))

    if score >= 90:
        level = "Excellent 🟢"
    elif score >= 75:
        level = "Good 🟡"
    elif score >= 60:
        level = "Average 🟠"
    else:
        level = "Needs Review 🔴"

    return {
        "score": score,
        "level": level,
        "ocr_confidence": round(ocr_confidence, 1)
    }



@app.route("/receipts", methods=["GET"])
def get_receipts():
        
        receipts = get_all_receipts()

        return jsonify(receipts)


@app.route("/dashboard", methods=["GET"])
def dashboard():
        summary = get_dashboard_summary()
        return jsonify(summary)



@app.route("/weather", methods=["GET"])
def get_weather():
    try:
        latitude = 29.9457
        longitude = 78.1642

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,relative_humidity_2m"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_mean"
            f"&timezone=auto"
            f"&forecast_days=14"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "current" not in data or "daily" not in data:
            return jsonify({"error": "Weather API returned unexpected data"}), 502

        temperature = data["current"]["temperature_2m"]
        humidity = data["current"]["relative_humidity_2m"]

        daily = data["daily"]
        rain_values = daily.get("precipitation_probability_mean", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])

        avg_rain_7d = sum(rain_values[:7]) / len(rain_values[:7]) if rain_values[:7] else 0
        avg_rain_14d = sum(rain_values) / len(rain_values) if rain_values else 0
        avg_max_temp = sum(max_temps) / len(max_temps) if max_temps else temperature
        avg_min_temp = sum(min_temps) / len(min_temps) if min_temps else temperature

        if avg_rain_14d > 65:
            crop = "Rice"
        elif avg_rain_14d < 25:
            crop = "Wheat"
        else:
            crop = "Sugarcane"

        return jsonify({
            "temperature": temperature,
            "humidity": humidity,
            "rain_today": rain_values[0] if rain_values else 0,
            "rain_7day_avg": round(avg_rain_7d, 1),
            "rain_14day_avg": round(avg_rain_14d, 1),
            "avg_max_temp_14d": round(avg_max_temp, 1),
            "avg_min_temp_14d": round(avg_min_temp, 1),
            "recommended_crop": crop
        })

    except requests.exceptions.RequestException as e:
        print("WEATHER API ERROR:", e)
        return jsonify({"error": "Weather service unavailable"}), 503
    except Exception as e:
        print("WEATHER ROUTE ERROR:", e)
        return jsonify({"error": str(e)}), 500
    
@app.route("/upload", methods=["POST"])
def upload_receipt():
        print("UPLOAD API CALLED")

        if "receipt" not in request.files:
            return jsonify({"error": "No file uploaded"}),400
        file = request.files["receipt"]

        if file.filename =="":  
            return jsonify({"error":"No selected file"}), 400
        
        filename = secure_filename(file.filename)

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        file.save(filepath)

        print("Saving done")
        
        print("Starting OCR")

        import time

        try:
            start = time.time()

            result_raw = get_reader().readtext(filepath, detail=1)

            extracted_text = "\n".join([r[1] for r in result_raw])
            ocr_confidences = [r[2] for r in result_raw]
            avg_ocr_confidence = (sum(ocr_confidences) / len(ocr_confidences)) * 100 if ocr_confidences else 0

            end = time.time()

            print("OCR TIME:", end - start)
            print("OCR Finished")

        
            print("\n========== OCR TEXT ==========")
            print(extracted_text)
            print("==============================")

            amount = "Not Found"
            payment_mode = "Not Found"
            date = "Not Found"
            crop = "Unknown"
            crop_keywords = {
                "Sugarcane": [
                    "sugarcane",
                    "sugar cane",
                    "sugar",
                    "butali sugar",
                    "sugar mills",
                    "cane"
                ],
                "Wheat": ["wheat"],
                "Rice": ["rice", "paddy"],
                "Maize": ["maize", "corn"],
                "Cotton": ["cotton"],
                "Bajra": ["bajra", "millet"]
            }

            text_lower = extracted_text.lower()

            for crop_name, keywords in crop_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    crop = crop_name
                    break
            print("Detected Crop:", crop)

            amount_match = re.search(r"(?:KES|₹|Rs\.?|INR)\s?[\d,]+(?:\.\d{2})?", extracted_text, re.IGNORECASE)
            if amount_match:
                amount = amount_match.group()

            date_match = re.search(r"\d{4}-\d{2}-\d{2}", extracted_text)
            if date_match:
                date = date_match.group()

            payment_match = re.search(r"(cash|card|upi|online|cheque)", extracted_text, re.IGNORECASE)

            
            if payment_match:
                payment_mode = payment_match.group()
            
            alerts = generate_ai_alerts(
            extracted_text,
            crop,
            amount
        )
            confidence = generate_ai_confidence(
            crop,
            amount,
            payment_mode,
            date,
            extracted_text,
            avg_ocr_confidence
)

            try:
                save_receipt(
                    filename,
                    crop,
                    amount,
                    payment_mode,
                    date,
                    extracted_text
                )
                print("DB SAVE DONE")
            except Exception as db_err:
                print("DB SAVE ERROR:", db_err)
            return jsonify({
                "message": "Receipt uploaded successfully",
                "text": extracted_text,
                "alerts": alerts,
                "confidence": confidence,
                "crop": crop,
                "amount": amount,
                "payment_mode": payment_mode,
                "date": date
    })
        except Exception as e:
            print("OCR ERROR:", e)

            return jsonify({
                "error": str(e)
            }), 500

print("========== ROUTES ==========")

for rule in app.url_map.iter_rules():
        print(rule)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))