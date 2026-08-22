const API_BASE = (location.hostname === "127.0.0.1" || location.hostname === "localhost") ? "http://127.0.0.1:5000" : "";

const DISTRICT_COORDS = {
  "Almora" :{lat:29.5971, lon:79.6591},
  "Bageshwar":{ lat: 29.8406, lon: 79.7714 },
  "Chamoli": { lat: 30.3165, lon: 79.3200 },
  "Champawat": { lat: 29.3350, lon: 80.0950 },
  "Dehradun": { lat: 30.3165, lon: 78.0322 },
  "Haridwar": { lat: 29.9457, lon: 78.1642 },
  "Nainital" :{ lat: 29.3919, lon: 79.4542 },
  "Pauri Garhwal":{ lat: 30.1462, lon: 78.7642 },
  "Pithoragarh":{ lat: 29.5829, lon: 80.2181 },
  "Rudraprayag":{ lat: 30.2844, lon: 78.9812 },
  "Tehri Garhwal":{ lat: 30.3900, lon: 78.4800 },
  "Udham Singh Nagar":{ lat: 28.9800, lon: 79.4000 },
  "Uttarkashi": { lat: 30.7268, lon: 78.4354 },
};

console.log("SCRIPT LOADED");
document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', function (e) {
    const href = this.getAttribute('href');

    if (href === '#') return;

    e.preventDefault();

    const target = document.querySelector(href);

    if (target) {
      target.scrollIntoView({
        behavior: 'smooth',
      });
    }
  });
});
const removeBtn = document.getElementById('removeBtn');
const fileName = document.getElementById('fileName');
const previewContainer = document.getElementById('previewContainer');
const fileInput = document.getElementById('receiptInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadArea = document.getElementById('uploadArea');
const stateSelect = document.getElementById('stateSelect');
const receiptTypeRadios = document.querySelectorAll(
  'input[name="receiptType"]',
);
const ocrUploadBlock = document.getElementById('ocrUploadBlock');
const manualSubmitBtn = document.getElementById('manualSubmitBtn');
const manualEntryBlock = document.getElementById('manualEntryBlock');

uploadArea.addEventListener('click', (e) => {
  if (e.target.id === 'removeBtn') return;

  fileInput.click();
});

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];

  if (!file) return;

  fileName.innerText = file.name;

  const reader = new FileReader();

  reader.onload = function (e) {
    previewContainer.innerHTML = `
            <img src="${e.target.result}" alt="Receipt Preview">
        `;

    removeBtn.style.display = 'block';

    uploadBtn.disabled = false;

    document.getElementById('uploadPlaceholder').style.display = 'none';
  };

  reader.readAsDataURL(file);
});

receiptTypeRadios.forEach((radio) => {
  radio.addEventListener('change', () => {
    if (radio.value === 'manual' && radio.checked) {
      ocrUploadBlock.style.display = 'none';
      manualEntryBlock.style.display = 'block';
    } else if (radio.checked) {
      ocrUploadBlock.style.display = 'block';
      manualEntryBlock.style.display = 'none';
    }
  });
});

console.log(uploadBtn);

uploadBtn.addEventListener('click', async (e) => {
  e.preventDefault();

  console.log('1 - BUTTON CLICKED');

  const file = fileInput.files[0];

  if (!file) {
    alert('Please select a receipt.');
    return;
  }

  const formData = new FormData();
  formData.append('receipt', file);

  formData.append(
    'receipt_type',
    document.querySelector('input[name = "receiptType"]:checked').value,
  );

  formData.append('state', stateSelect.value);

  const status = document.getElementById('status');

  const resultBox = document.getElementById('resultBox');

  const detectedGrid = document.getElementById('detectedGrid');

  const rawText = document.getElementById('rawText');

  resultBox.style.display = 'none';
  status.className = 'loading';
  status.innerText = '⏳ Processing receipt, please wait...';
  uploadBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });

    console.log('3 - Response received');

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || ('Server returned status' + response.status));
    }

    

    console.log('Full Response');
    console.log(result);

    console.log('ALERTS');
    console.log(result.alerts);

    await loadDashboard();
    await loadHistory();
    
    if (result.verification && result.verification.status ==="Possible Underpayment") {
      document.getElementById("heroAlert").innerText = `⚠ Underpayment Detected (₹${result.verification.difference.toLocaleString()})`;
    }

    const aiContainer = document.getElementById('aiAlerts');

    aiContainer.innerHTML = '';

    result.alerts.forEach((alert) => {
      aiContainer.innerHTML += `
            <div class="alert-card ${alert.type}">
                <h3>${alert.title}</h3>
                <p>${alert.message}</p>
            
            </div>
        `;
  });

    if (result.error) {
      throw new Error(result.error);
    }
    const text = result.text || '';

    const amountMatch = text.match(/(?:KES|₹|Rs\.?)\s?[\d,]+\.\d{2}/i);
    const dateMatch = text.match(/\d{4}-\d{2}-\d{2}/);
    const paymentMatch = text.match(
      /payment method[\s\S]{0,20}?(cash|card|upi|cheque|online)/i,
    );

    detectedGrid.innerHTML = `
        
    <div class= "detected-item">
            <span>Amount</span>
            <strong>${amountMatch ? amountMatch[0] : 'Not found'} </strong>
        </div>

        <div class ="detected-item">
            <span>Payment Mode</span>
            <strong>${paymentMatch ? paymentMatch[1] : 'Not found'} </strong>
        </div>

        <div class="detected-item">
            <span>Date</span>
            <strong>${dateMatch ? dateMatch[0] : 'Not found'}</strong>
        </div>
        `;

    rawText.innerText = text;

    document.getElementById('aiSummary').innerHTML = `
        
        <h3>🤖 AI Summary</h3> 
        
        <p><b>🌾 Crop:</b> ${result.crop}</p>

        <p><b>💰 Amount:</b> ${result.amount}</p>

        <p><b>💳 Payment:</b> ${result.payment_mode}</p>

        <p><b>📅 Date:</b> ${result.date}</p>
         
        `;

    document.getElementById("aiRecommendation").style.display ="none";
    document.getElementById("verificationCard").style.display = "none";
    document.getElementById("aiConfidence").style.display = "none";
    document.getElementById("aiAlerts").style.display = "none";
    document.querySelector(".raw-title").style.display = "none";
    document.getElementById("rawText").style.display = "none";


    let recommendation = '';

    const payment = (result.payment_mode || '').toLowerCase();

    if (payment === 'cash') {
      recommendation =
        '💡 Cash payment detected. Consider using digital payments for better record tracking.';
    } else if (payment === 'upi') {
      recommendation =
        '✅ Digital payment detected. Transaction tracking will be easier.';
    } else {
      recommendation = '📄 Receipt stored successfully for future analytics.';
    }

    document.getElementById('aiRecommendation').innerHTML = `
        <h3>🧠 AI Recommendation</h3>
        
        <p>${recommendation}</p>
        
        `;

    document.getElementById('aiConfidence').innerHTML = `
            <h3>🎯 AI Confidence</h3>
            <h2>${result.confidence.score}%</h2>
            <p><b>${result.confidence.level}</b></p>
            <p style="font-size:13px; color:#9ae6b4;">Based on OCR clarity: ${result.confidence.ocr_confidence}%</p>
        `;

    if (result.verification) {
      const verification = result.verification;

      const badgeColor =
        verification.status === 'Possible Underpayment' ? '#ef4444' : '#22c55e';

      document.getElementById('verificationCard').innerHTML = `
                <h3>🏛 Government Payment Verification</h3>

                <p><b>📍 State:</b> ${verification.state}</p>

                <p><b>📜 ${verification.rate_type} Rate:</b>
                ₹${verification.government_rate} / Quintal</p>

                <p><b>💰 Expected Amount:</b>
                ₹${verification.expected_amount.toLocaleString()}</p>

                <p><b>💵 Received Amount:</b>
                ₹${verification.received_amount.toLocaleString()}</p>

                <p><b>📉 Difference:</b>
                ₹${Math.abs(verification.difference).toLocaleString()}</p>

                <p style="
                    color:${badgeColor};
                    font-weight:bold;
                    font-size:18px;
                ">
                    ${verification.status}
                </p>

                <hr>

                <small>
                    ✔ Last Verified :
                    ${verification.last_verified}
                </small>

            `;
    }

    document.getElementById("aiRecommendation").style.display ="block";
    document.getElementById("verificationCard").style.display = "block";
    document.getElementById("aiConfidence").style.display = "block";
    document.getElementById("aiAlerts").style.display ="block";
    document.querySelector(".raw-title").style.display ="block";
    document.getElementById("rawText").style.display = "block";

    
    resultBox.style.display = 'block';

    status.className = '';
    status.innerText = '✅ Receipt processed successfully.';
  } catch (err) {
    console.error(err);
    status.className = 'error';
    status.innerText = '❌ Something went wrong: ' + err.message;
  } finally {
    uploadBtn.disabled = false;
  }
});
removeBtn.addEventListener('click', (e) => {
  e.stopPropagation();

  fileInput.value = '';
  previewContainer.innerHTML = '';
  fileName.innerText = '';

  removeBtn.style.display = 'none';

  uploadBtn.disabled = true;

  document.getElementById('uploadPlaceholder').style.display = 'block';
});
async function loadDashboard() {
  try {
    const response = await fetch(`${API_BASE}/dashboard`);
    const data = await response.json();

    document.getElementById('totalReceipts').innerText =
      data.total_receipts + ' Receipts';

    document.getElementById('totalRevenue').innerText =
      '₹' + Number(data.total_revenue).toLocaleString();

    document.getElementById('pendingReceipts').innerText =
      data.pending_receipts + ' Pending';

    document.getElementById('pendingAmount').innerText =
      '₹' + Number(data.pending_amount).toLocaleString();
    
    document.getElementById('underpaidCount').innerText = data.underpaid_receipts +' Receipts';

    document.getElementById('underpaidAmount').innerText = '₹' + Number(data.underpayment_total).toLocaleString('en-IN');

    document.getElementById('aiAlert').innerText = 

      data.pending_receipts > 0
        ? `${data.pending_receipts} payment(s) pending`
        : 'No Alerts';

    document.getElementById('aiAlert').innerText =
    data.pending_receipts > 0
        ? `${data.pending_receipts} payment(s) pending`
        : 'No Alerts';

// ===== HERO DASHBOARD =====
    document.getElementById("heroRevenue").innerText =
        "₹" + Number(data.total_revenue).toLocaleString("en-IN");

    document.getElementById("heroSugarcane").innerText =
        `${data.total_receipts} Receipts`;

    document.getElementById("heroPending").innerText =
        "₹" + Number(data.pending_amount).toLocaleString("en-IN");

    document.getElementById("heroAlert").innerText =
    data.pending_receipts > 0
        ? `⚠ ${data.pending_receipts} Payments Pending`
        : data.underpaid_receipts > 0
            ? `⚠ Underpayment Detected (₹${Number(data.underpayment_total).toLocaleString('en-IN')})`
            : "✅ No Pending Payments";
        

    } catch (err) {
        console.error('Dashboard Error:', err);
  }
}

loadDashboard();

async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE}/receipts`);
    const receipts = await response.json();

    const historyBody = document.getElementById('historyBody');

    historyBody.innerHTML = '';

    receipts.forEach((receipt) => {
      historyBody.innerHTML += `
                        <tr>
                            <td>${receipt.receipt_name}</td>
                            <td>${receipt.receipt_type || '-'}</td>
                            <td>${receipt.payment_status || '-'}</td>
                            <td>${receipt.days_pending || 0}</td>
                            <td>${receipt.expected_payment_date || '-'}</td>
                            <td>${receipt.amount}</td>
                            <td>${receipt.crop}</td>
                        </tr>
                    `;
});
  } catch (err) {
    console.error('History Error:', err);
  }
}
loadHistory();

async function loadWeather() {

  console.log("loadWeather started");

  const fetchWeather = (lat, lon) => {
    
    console.log("Fetching:", lat, lon);

    fetch(`${API_BASE}/weather?lat=${lat}&lon=${lon}`)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          document.getElementById('weatherTempMain').innerText = '⚠️ Unavailable';
          document.getElementById('weatherTempRange').innerText = '';
          document.getElementById('cropSuggestion').innerText = 'N/A';
          return;
        }

        const tempEl = document.getElementById('weatherTempMain');
        tempEl.innerText = `${data.temperature}°C`;
        tempEl.className = 'weather-main-value ' + getTempClass(data.temperature);

        document.getElementById('weatherTempRange').innerText =
          `14-day range: ${data.avg_min_temp_14d}° – ${data.avg_max_temp_14d}°C`;

        const weatherIcon = getRainEmoji(data.rain_today);
        document.querySelector('#weatherCard h3').innerText =
          `${weatherIcon} AI Weather Intelligence`;

        document.getElementById('rainBarToday').style.width = `${data.rain_today}%`;
        document.getElementById('rainValueToday').innerText = `${data.rain_today}%`;

        document.getElementById('rainBar7d').style.width = `${data.rain_7day_avg}%`;
        document.getElementById('rainValue7d').innerText = `${data.rain_7day_avg}%`;

        document.getElementById('rainBar14d').style.width = `${data.rain_14day_avg}%`;
        document.getElementById('rainValue14d').innerText = `${data.rain_14day_avg}%`;

        document.getElementById('humidityCircle').innerText = `${data.humidity}%`;
        document.getElementById('humidityStatus').innerText = getHumidityStatus(data.humidity);

        document.getElementById('cropSuggestion').innerText = data.recommended_crop;
      })
      .catch(err => console.error('Weather Error:', err));
  };

  const districtSelect = document.getElementById('districtSelect');
  const selectedDistrict = districtSelect ? districtSelect.value : 'auto';

  if (selectedDistrict !== 'auto' && DISTRICT_COORDS[selectedDistrict]) {
    const coords = DISTRICT_COORDS[selectedDistrict];
    fetchWeather(coords.lat, coords.lon);
  } else if (navigator.geolocation){
    navigator.geolocation.getCurrentPosition(
      (pos) => fetchWeather(pos.coords.latitude, pos.coords.longitude),
      () => fetchWeather(29.9457, 78.1642) // Fallback to Haridwar if geolocation fails
    );

  } else{
    fetchWeather(29.9457, 78.1642);
    }
  }
  document.addEventListener('DOMContentLoaded', () => {
    const districtSelect = document.getElementById('districtSelect');
    if (districtSelect) {
      districtSelect.addEventListener('change', loadWeather);
    }
  });

console.log("About to call loadWeather");
loadWeather();

function getTempClass(temp) {
  if (temp < 20) return 'temp-cold';
  if (temp < 30) return 'temp-mild';
  if (temp < 40) return 'temp-hot';
  return 'temp-extreme';
}

function getRainEmoji(rainPercent) {
  if (rainPercent < 20) return '☀️';
  if (rainPercent < 50) return '🌦';
  if (rainPercent < 75) return '🌧';
  return '⛈';
}

function getHumidityStatus(humidity) {
  if (humidity < 30) return 'Low';
  if (humidity <= 70) return 'Optimal';
  return 'High';
}



manualSubmitBtn.addEventListener('click', async () => {
  const millName = document.getElementById('millName').value.trim();
  const deliveryDate = document.getElementById('deliveryDate').value;
  const quantityValue = document.getElementById('quantityValue').value;
  const quantityUnit = document.getElementById('quantityUnit').value;
  const manualAmount = document.getElementById('manualAmount').value;

  if (!millName || !deliveryDate || !quantityValue) {
    alert('Please fill Mill Name, Delivery Date, and Quantity.');
    return;
  }
  const status = document.getElementById('status');
  status.className = 'loading';
  status.innerText = '⏳ Saving manual entry...';

  try {
    const response = await fetch(`${API_BASE}/manual-entry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mill_name: millName,
        delivery_date: deliveryDate,
        quantity: quantityValue,
        unit: quantityUnit,
        amount: manualAmount || null,
        state: stateSelect.value,
      }),
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    await loadDashboard();
    await loadHistory();

    status.className = '';
    status.innerText = '✅ Manual entry saved successfully.';

    document.getElementById('resultBox').style.display = 'block';

    document.getElementById('aiSummary').innerHTML = `
         <h3>📝 Manual Entry Summary</h3>
            <p><b>🏭 Mill:</b> ${result.mill_name}</p>
            <p><b>📦 Quantity:</b> ${result.quantity_quintals} Quintals</p>
            <p><b>💰 Expected Amount:</b> ₹${result.expected_amount ?? 'Not Available'}</p>
            <p><b>💸 Pending Amount:</b> ₹${result.pending_amount ?? '0'}</p>
            <p><b>📅 Delivery Date:</b> ${result.delivery_date}</p>
            <p><b>📌 Status:</b> ${result.payment_status}</p>
        `;
        document.getElementById("aiRecommendation").style.display = "none";
        document.getElementById("verificationCard").style.display = "none";
        document.getElementById("aiConfidence").style.display = "none";
        document.getElementById("aiAlerts").style.display = "none";
        document.querySelector(".raw-title").style.display = "none";
        document.getElementById("rawText").style.display = "none";
  } catch (err) {
    console.error(err);
    status.className = 'error';
    status.innerText = '❌ Something went wrong: ' + err.message;
  }
}); 


