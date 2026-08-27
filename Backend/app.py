from flask import Flask ,request, jsonify
from flask_cors import CORS 
import os
import easyocr
from werkzeug.utils import secure_filename 
from database.db import (
            create_forecast_log_table,
            create_receipts_table,
            generate_receipt_hash,
            upgrade_receipts_table,
            create_rates_table,
            seed_rates,
            get_rate,
            save_receipt,
            get_all_receipts,
            get_dashboard_summary,
            find_matching_delivery,
            mark_delivery_paid,
            is_duplicate_receipt,
            save_forecast,
            validate_pending_forecasts,
            get_forecast_accuracy,
        )
import re
import requests
import traceback
from datetime import datetime

reader = None
def get_reader():
        global reader
        if reader is None:
            reader = easyocr.Reader(['en'], gpu=False)
        return reader

app =Flask(__name__)
CORS(app)

create_receipts_table()
upgrade_receipts_table()
create_rates_table()
create_forecast_log_table()
seed_rates()



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
def normalize_date(text):
        # Pehle ISO format try karo: 2026-07-20
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return match.group()

        # Fir DD-MM-YYYY ya DD/MM/YYYY try karo: 20-07-2026 ya 20/07/2026
        match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", text)
        if match:
            day, month, year = match.groups()
            try:
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except (ValueError, TypeError):
                return "Not Found"

        return "Not Found"

def clean_amount_value(amount):
        if not amount or amount == "Not Found":
            return None

        match = re.search(r"\d[\d,]*(?:\.\d+)?", amount)

        if not match:
            return None

        cleaned = match.group().replace(",", "")

        return float(cleaned)


def normalize_currency(amount_str):          # 👈 YE NAYA FUNCTION ADD KARO
        if not amount_str or amount_str == "Not Found":
            return amount_str
        return re.sub(r"(KES|Rs\.?|INR)", "₹", amount_str, flags=re.IGNORECASE)


@app.route("/receipts", methods=["GET"])
def get_receipts():
            
            receipts = get_all_receipts_with_status()

            return jsonify(receipts)


def calculate_days_pending(delivery_date_str):
        if not delivery_date_str or delivery_date_str == "Not Found":
            return None

        try:
            delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d")
            today = datetime.now()
            days = (today - delivery_date).days
            return days if days >= 0 else None
        except (ValueError, TypeError):
            return None


def get_risk_tier(days_pending):
        if days_pending is None:
            return None
        if days_pending <= 14:
            return "Normal"
        elif days_pending <= 30:
            return "Warning"
        else:
            return "High Risk"


def get_all_receipts_with_status():
        receipts = get_all_receipts()

        for r in receipts:
            if r.get("payment_status") == "pending":
                days_pending = calculate_days_pending(r.get("delivery_date"))
                r["days_pending"] = days_pending
                r["risk_tier"] = get_risk_tier(days_pending)
            else:
                r["days_pending"] = None
                r["risk_tier"] = None

        return receipts

@app.route("/dashboard", methods=["GET"])
def dashboard():
            summary = get_dashboard_summary()
            return jsonify(summary)



@app.route("/weather", methods=["GET"])
def get_weather():
        try:
            latitude = request.args.get("lat", default = 29.9457 , type = float)
            longitude = request.args.get("lon", default = 78.1642, type = float)

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

                        district_key = f"{latitude},{longitude}"

            # ===== Aaj ka current data = "actual" hai purani pending forecasts ke liye =====
            validate_pending_forecasts(district_key, temperature, humidity, rain_values[0] if rain_values else 0)

            # ===== Aaj ka naya 14-din ka forecast save karo future validation ke liye =====
            daily_dates = daily.get("time", [])
            for i in range(len(daily_dates)):
                if i < len(max_temps) and i < len(min_temps):
                    predicted_temp = (max_temps[i] + min_temps[i]) / 2
                    predicted_rain = rain_values[i] if i < len(rain_values) else 0
                    save_forecast(
                        district=district_key,
                        target_date=daily_dates[i],
                        predicted_temp=round(predicted_temp, 1),
                        predicted_humidity=humidity,  # approx, kyunki daily humidity forecast nahi hai abhi
                        predicted_rain_pct=predicted_rain
                    )

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
@app.route("/forecast-accuracy", methods=["GET"])
def forecast_accuracy():
     district = request.args.get("district", None)
     days = request.args.get("days",default = 7, type=int)
     accuracy = get_forecast_accuracy(district=district, days=days)
     if accuracy is None:
          return jsonify({"message": "Not enough validated data yet"}), 200
     return jsonify(accuracy)
        
@app.route("/upload", methods=["POST"])

def upload_receipt():
        
            print("UPLOAD API CALLED")

            if "receipt" not in request.files:
                return jsonify({"error": "No file uploaded"}),400
            file = request.files["receipt"]

            state = request.form.get("state", "Uttarakhand")

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

                receipt_hash = generate_receipt_hash(extracted_text)

                if is_duplicate_receipt(receipt_hash):
                     print("DUPLICATE RECEIPT DETECTED!!")
                     return jsonify({"error": "This receipt has already been uploaded."}), 409
                

            
                print("\n========== OCR TEXT ==========")
                print(extracted_text)
                print("\n=========== DEBUG ===========")

                

                print("All Currency Matches :",
                    re.findall(
                        r"(?:KES|₹|Rs\.?|INR)\s?[\d,]+(?:\.\d{2})?",
                        extracted_text,
                        re.IGNORECASE
                    )
                )

                print("=============================\n")

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

                # Pehle labeled "Amount Paid" / "Total" wala number dhoondo — zyada reliable
                amount_match = re.search(
                    r"(?:Amount\s*Paid|Invoice\s*Total|Grand\s*Total|Total\s*Amount)[:\s]*"
                    r"((?:KES|₹|Rs\.?|INR)\s?[\d,]+(?:\.\d{2})?)",
                    extracted_text,
                    re.IGNORECASE
            )
            

                print("Amount Match:", amount_match)

                if amount_match:

                    amount = amount_match.group(1)
                    print("Matched Amount:", amount)
                    
                    amount = normalize_currency(amount)  


                else:
                    # Fallback: agar labeled amount nahi mila, to LAST currency number lo
                    # (receipts mein total/paid amount aksar sabse neeche hota hai, rate upar)
                    generic_matches = re.findall(
                        r"(?:KES|₹|Rs\.?|INR)\s?[\d,]+(?:\.\d{2})?",
                        extracted_text,
                        re.IGNORECASE
                    )
                    amount = generic_matches[-1] if generic_matches else "Not Found"
                    amount = normalize_currency(amount)  

                weight = "Not Found"
                weight_quintals = None

                weight_match = re.search(
                    r"(\d+(?:\.\d+)?)\s*(ton|tonne|tons|quintal|qtl|kg)",
                    extracted_text,
                    re.IGNORECASE

                    )
                
                if weight_match:
                    
                    value =float(weight_match.group(1))

                    unit = weight_match.group(2).lower()

                    if unit in ["ton", "tons", "tonne"]:
                        weight_quintals = value * 10 

                    elif unit == "kg":
                        weight_quintals = value / 100
                    
                    else:
                        weight_quintals = value

                    weight = f"{value} {unit}"

                    print("Weight:", weight)

                    print("Weight in Quintals:" , weight_quintals)

                if amount_match:
                    amount = amount_match.group(1)

                date = normalize_date(extracted_text)

                payment_match = re.search(r"(cash|card|upi|online|cheque)", extracted_text, re.IGNORECASE)

                
                if payment_match:
                    payment_mode = payment_match.group()

                verification = None 

                rate_info = get_rate(crop, state)

                
                print("========== VERIFY DEBUG ==========")
                print("Amount:", amount)
                print("Weight Quintals:", weight_quintals)
                print("Crop:", crop)
                print("State:", state)
                print("Rate Info:", rate_info)
                print("==================================")

                if rate_info and weight_quintals is not None and amount != "Not Found":
                    
                    
                    try:
                        
                        received_amount = clean_amount_value(amount)

                        print("Amount:", amount)
                        print("Received Amount:", received_amount)
                        print("Weight Quintals:", weight_quintals)
                        print("Crop:", crop)

                        if received_amount is None:
                            raise ValueError("Invalid Amount")



                        expected_amount = (
                            rate_info["rate_per_quintal"] *
                            weight_quintals
                        )

                        pending_amount = expected_amount

                        if received_amount is not None:
                                pending_amount = max(0, round(expected_amount - received_amount, 2))
                        else:
                                pending_amount = expected_amount

                        pending_amount = max(
                                0,
                                round(expected_amount - (received_amount or 0), 2)
                            )
                            
                        difference = round (
                            expected_amount - received_amount,
                            2
                        )

                        verification = {
                                    "state":state,
                                
                                    "rate_type": rate_info["rate_type"],

                                    "government_rate":
                                        rate_info["rate_per_quintal"],

                                    "expected_amount":
                                        round(expected_amount,2),

                                    "received_amount":
                                        received_amount,

                                    "difference":
                                        difference,

                                    "status":
                                        "Possible Underpayment"
                                        if difference > 100
                                        else "Payment Looks Correct",

                                    "source":
                                        rate_info["source_url"],

                                    "last_verified":
                                        rate_info["last_verified"]

                                }

                    except Exception as e:

                        print("Verification Error:", e)        
                    
                alerts = generate_ai_alerts(
                extracted_text,
                crop,
                amount
            )
                
                if verification:
                    
                    if verification["status"] == "Possible Underpayment":
                        
                        alerts.append({
                            "type": "danger",
                            "title": "Government Verification",
                            "message": f"Possible underpayment detected. Difference  ₹{verification['difference']}"
                        })
                    else:
                        
                        alerts.append({
                            "type": "success",
                            "title": "Government Verification",
                            "message" :"Payment matches government reference rate."
                        })

                from datetime import datetime, timedelta

                expected_payment_date = None 
                days_pending = 0 

                if date and date != "Not Found":

                    try: 

                        delivery_date_obj = datetime.strptime(date, "%Y-%m-%d")

                        expected_payment_date = (
                            delivery_date_obj + timedelta(days=14)

                        ).strftime("%Y-%m-%d")

                        today = datetime.today()

                        days_pending = max(
                            (today - delivery_date_obj).days - 14,
                            0
                        )
                    except Exception as e:
                        print("Date Calculation Error:", e)
                    
                confidence = generate_ai_confidence(
                crop,
                amount,
                payment_mode,
                date,
                extracted_text,
                avg_ocr_confidence
    )

                receipt_type = request.form.get("receipt_type", "payment")
                payment_status = "pending" if receipt_type == "delivery" else "paid"
                expected_amount_to_save = verification["expected_amount"] if verification else None

                try:
                    save_receipt(
                        receipt_name=filename,
                        crop=crop,
                        amount=amount,
                        payment_mode=payment_mode,
                        date=date,
                        raw_text=extracted_text,
                        receipt_type=receipt_type,
                        delivery_date=date if (receipt_type == "delivery" and date != "Not Found") else None,
                        payment_status=payment_status,
                        expected_amount=expected_amount_to_save,
                        quantity_quintals=weight_quintals,
                        is_manual_entry=0,
                        mill_name=None,
                        expected_payment_date=expected_payment_date,
                        days_pending=days_pending,
                        receipt_hash=receipt_hash
                    )
                    print("DB SAVE DONE")

                    if receipt_type == "payment" and weight_quintals is not None:

                        matched_delivery = find_matching_delivery(
                            crop,
                            weight_quintals
                        )
                        if matched_delivery:
                            mark_delivery_paid(matched_delivery["id"])
                            print("Manual delivery matched automatically")

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
                    "date": date,
                    "weight": weight,
                    "weight_quintals": weight_quintals,
                    "verification" : verification
        })
            except Exception as e:
                print("========== VERIFICATION TRACEBACK ==========")
                traceback.print_exc()
                print("============================================")

                return jsonify({
                    "error": str(e)
                }), 500

def convert_to_quintals(value, unit):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        unit = (unit or "").lower()

        if unit in ["ton", "tons", "tonne"]:
            return value * 10
        elif unit == "kg":
            return value / 100
        else:  
            return value


@app.route("/manual-entry", methods=["POST"])
def manual_entry():
        try:
            data = request.get_json()

            mill_name = data.get("mill_name")
            delivery_date = data.get("delivery_date")
            quantity = data.get("quantity")
            unit = data.get("unit", "quintal")
            amount = data.get("amount")
            state = data.get("state", "Uttarakhand")

            if not mill_name or not delivery_date or not quantity:
                return jsonify({"error": "Mill name, delivery date and quantity are required"}), 400

            quantity_quintals = convert_to_quintals(quantity, unit)

            if quantity_quintals is None:
                return jsonify({"error": "Invalid quantity"}), 400

            rate_info = get_rate("Sugarcane", state)

            expected_amount = None
            if rate_info:
                expected_amount = round(rate_info["rate_per_quintal"] * quantity_quintals, 2)

            received_amount = None
            payment_status = "pending"

            if amount:
                try:
                    received_amount = float(amount)
                    payment_status = "paid"
                except (TypeError, ValueError):
                    received_amount = None

            pending_amount = None                                   

            if expected_amount is not None:                         
                pending_amount = round(expected_amount - (received_amount or 0), 2)  
                if pending_amount < 0:                               
                    pending_amount = 0         

            save_receipt(
                receipt_name=f"Manual Entry - {mill_name}",
                crop="Sugarcane",
                amount=str(received_amount) if received_amount is not None else "0",
                payment_mode="Not Found",
                date=delivery_date,
                raw_text="Manual entry - farmer did not have a formal receipt.",
                receipt_type="manual_delivery",
                delivery_date=delivery_date,
                payment_status=payment_status,
                expected_amount=expected_amount,
                quantity_quintals=quantity_quintals,
                is_manual_entry=1,
                mill_name = mill_name,
                expected_payment_date = None,
                days_pending = 0
            )

            return jsonify({
                "message": "Manual entry saved successfully",
                "mill_name": mill_name,
                "delivery_date": delivery_date,
                "quantity_quintals": quantity_quintals,
                "expected_amount": expected_amount,
                "received_amount": received_amount,
                "pending_amount": pending_amount,
                "payment_status": payment_status,
                "rate_info": rate_info
            })

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
        
print("========== ROUTES ==========")

for rule in app.url_map.iter_rules():
            print(rule)

if __name__ == "__main__":
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
        








