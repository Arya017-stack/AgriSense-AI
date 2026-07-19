    document.querySelectorAll('a[href^="#"]').forEach(link => {

        link.addEventListener("click", function(e){

            const href = this.getAttribute("href");

            if(href === "#") return;

            e.preventDefault();

            const target = document.querySelector(href);

            if(target){
                target.scrollIntoView({
                    behavior:"smooth"
                });
            }

        });

    });
    const removeBtn=document.getElementById("removeBtn");
    const fileName = document.getElementById("fileName");
    const previewContainer = document.getElementById("previewContainer");
    const fileInput = document.getElementById("receiptInput");
    const uploadBtn = document.getElementById("uploadBtn");
    const uploadArea = document.getElementById("uploadArea");

    uploadArea.addEventListener("click", (e) => {

        if(e.target.id === "removeBtn") return;

        fileInput.click();

    });

    fileInput.addEventListener("change", () => {

        const file = fileInput.files[0];

        if(!file) return;

        fileName.innerText = file.name;

        const reader = new FileReader();

        reader.onload = function(e) {

        previewContainer.innerHTML = `
            <img src="${e.target.result}" alt="Receipt Preview">
        `;

        removeBtn.style.display = "block";

        uploadBtn.disabled = false;

        document.getElementById("uploadPlaceholder").style.display = "none";
    };

        reader.readAsDataURL(file);

    });
    console.log(uploadBtn);

    uploadBtn.addEventListener("click", async (e) => {

        e.preventDefault();

        console.log("1 - BUTTON CLICKED");

        const file = fileInput.files[0];

        if (!file) {
            alert("Please select a receipt.");
            return;
        }

        const formData = new FormData();
        formData.append("receipt", file);

        const status = document.getElementById("status");
        
        const resultBox =document.getElementById("resultBox");
        
        const detectedGrid = document.getElementById("detectedGrid");
        
        const rawText = document.getElementById("rawText");

        resultBox.style.display="none";
        status.className = "loading";
        status.innerText = "⏳ Processing receipt, please wait...";
        uploadBtn.disabled = true;

        try {

          const response = await fetch("http://127.0.0.1:5000/upload", {
            method:"POST",
            body: formData
    });

    console.log("3 - Response received");

    if (!response.ok){
        throw new Error ("Server returned status " + response.status);
    }

    const result = await response.json();

    console.log("FUll Response");
    console.log(result);

    console.log("ALERTS");
    console.log(result.alerts);

    await loadDashboard();
    await loadHistory();

    const aiContainer = document.getElementById("aiAlerts");

    aiContainer.innerHTML ="";

    result.alerts.forEach(alert => {

        aiContainer.innerHTML += `
            <div class="alert-card ${alert.type}">
                <h3>${alert.title}</h3>
                <p>${alert.message}</p>
            
            </div>
        `;

    });

    if (result.error){
        throw new Error(result.error)

    }
    const text = result.text || "";

    const amountMatch = text.match(/(?:KES|₹|Rs\.?)\s?[\d,]+\.\d{2}/i);
    const dateMatch = text.match(/\d{4}-\d{2}-\d{2}/);
    const paymentMatch = text.match(/payment method[\s\S]{0,20}?(cash|card|upi|cheque|online)/i);

    detectedGrid.innerHTML = `
        
    <div class= "detected-item">
            <span>Amount</span>
            <strong>${amountMatch ? amountMatch[0] : "Not found"} </strong>
        </div>

        <div class ="detected-item">
            <span>Payment Mode</span>
            <strong>${paymentMatch ? paymentMatch[1] : "Not found"} </strong>
        </div>

        <div class="detected-item">
            <span>Date</span>
            <strong>${dateMatch ? dateMatch[0] : "Not found"}</strong>
        </div>
        `;

        rawText.innerText = text;

        document.getElementById("aiSummary").innerHTML = `
        
        <h3>🤖 AI Summary</h3> 
        
        <p><b>🌾 Crop:</b> ${result.crop}</p>

        <p><b>💰 Amount:</b> ${result.amount}</p>

        <p><b>💳 Payment:</b> ${result.payment_mode}</p>

        <p><b>📅 Date:</b> ${result.date}</p>
         
        `;


        let recommendation ="";

        const payment = (result.payment_mode || "").toLowerCase();

        if(payment === "cash"){   
            recommendation = "💡 Cash payment detected. Consider using digital payments for better record tracking.";

        }

        else if(payment === "upi"){
            recommendation =  "✅ Digital payment detected. Transaction tracking will be easier.";
        }

        else{
            recommendation =  "📄 Receipt stored successfully for future analytics.";
        }

        document.getElementById("aiRecommendation").innerHTML =`
        <h3>🧠 AI Recommendation</h3>
        
        <p>${recommendation}</p>
        
        `;

        document.getElementById("aiConfidence").innerHTML = `
            <h3>🎯 AI Confidence</h3>
            <h2>${result.confidence.score}%</h2>
            <p><b>${result.confidence.level}</b></p>
            <p style="font-size:13px; color:#9ae6b4;">Based on OCR clarity: ${result.confidence.ocr_confidence}%</p>
        `;
        resultBox.style.display ="block";

        status.className="";
        status.innerText = "✅ Receipt processed successfully.";

    } catch(err){
        console.error(err);
        status.className ="error";
        status.innerText="❌ Something went wrong: " + err.message;

    }   finally{
        uploadBtn.disabled =false;
    }
    });    
        removeBtn.addEventListener("click", (e) => {

        e.stopPropagation();

        fileInput.value = "";
        previewContainer.innerHTML = "";
        fileName.innerText = "";

        removeBtn.style.display = "none";

        uploadBtn.disabled = true;

        document.getElementById("uploadPlaceholder").style.display = "block";

    });
        async function loadDashboard(){
            try{
                const response= await fetch ("http://127.0.0.1:5000/dashboard");
                const data = await response.json();

                document.getElementById("totalReceipts").innerText = data.total_receipts + " Receipts";


                document.getElementById("totalRevenue").innerText = "KES " +Number(data.total_revenue).toLocaleString();

                document.getElementById("latestPayment").innerText = data.latest_payment;

                document.getElementById("aiAlert").innerText = data.latest_payment === "N/A"
                    ?"No Alerts" 
                    : "Payment: " + data.latest_payment;


            }   

            catch(err){
                console.error("Dashboard Error:", err);
            }
        }

        loadDashboard();

        async function loadHistory(){

            try{
                const response = await fetch("http://127.0.0.1:5000/receipts");
                const receipts = await response.json();

                const historyBody = document.getElementById("historyBody");

                historyBody.innerHTML = "";

                receipts.forEach(receipt => {
                    historyBody.innerHTML += `
                        <tr>
                            <td>${receipt.receipt_name}</td>
                            <td>${receipt.amount}</td>
                            <td>${receipt.payment_mode}</td>
                            <td>${receipt.date}</td>
                            <td>${receipt.crop}</td>
                        </tr>
                    `;
                });
            }
            catch(err){
                console.error("History Error:", err);
            }
        }
        loadHistory();


        async function loadWeather(){

    try{
        const response = await fetch("http://127.0.0.1:5000/weather");
        const data = await response.json();

        if (data.error) {
            document.getElementById("weatherTemp").innerHTML = "⚠️ Weather unavailable";
            document.getElementById("weatherHumidity").innerHTML = "";
            document.getElementById("weatherRain").innerHTML = "";
            document.getElementById("cropSuggestion").innerHTML = "";
            return;
        }

        document.getElementById("weatherTemp").innerHTML =
            `🌡 ${data.temperature}°C (14d: ${data.avg_min_temp_14d}–${data.avg_max_temp_14d}°C)`;

        document.getElementById("weatherHumidity").innerHTML =
            `💧 Humidity: ${data.humidity}%`;

        document.getElementById("weatherRain").innerHTML =
            `🌧 Rain — Today: ${data.rain_today}% | 7d avg: ${data.rain_7day_avg}% | 14d avg: ${data.rain_14day_avg}%`;

        document.getElementById("cropSuggestion").innerHTML =
            `🌾 Recommended Crop (14-day trend): <b>${data.recommended_crop}</b>`;

    }
    catch(err){
        console.error("Weather Error:", err);
    }
}

loadWeather();