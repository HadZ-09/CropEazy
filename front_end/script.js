const API_BASE = window.location.origin.includes("5500") ||
    window.location.protocol === "file:"
    ? "http://127.0.0.1:8000"
    : window.location.origin;

const AUTH_TOKEN_KEY = "cropeazy_auth_token";
const AUTH_USER_KEY = "cropeazy_auth_user";
const LOCATION_PROMPT_KEY = "cropeazy_location_prompt_seen";

let currentMode = "crop";
let cropPrices = {};
let lastCropResult = null;
let lastYieldResult = null;
let lastYieldInput = null;
let lastRecommendedCrop = null;
let locationContext = null;
let currentUser = null;
let lastKnownCoords = null;

function getAuthToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
}

function authHeaders(extra = {}) {
    const headers = { ...extra };
    const token = getAuthToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return headers;
}

function isLoggedIn() {
    return Boolean(getAuthToken());
}

function updateAuthUi() {
    const loggedIn = isLoggedIn();
    document.getElementById("nav-login-btn").classList.toggle("hidden", loggedIn);
    document.getElementById("nav-logout-btn").classList.toggle("hidden", !loggedIn);

    const label = document.getElementById("nav-user-label");
    if (loggedIn && currentUser) {
        label.textContent = `${currentUser.name} · ${currentUser.phone}`;
        label.classList.remove("hidden");
    } else {
        label.classList.add("hidden");
        label.textContent = "";
    }
}

function showPage(pageId) {
    const publicPages = ["page-login", "page-how"];

    if (!publicPages.includes(pageId) && !isLoggedIn()) {
        pageId = "page-login";
    }

    document.querySelectorAll(".page").forEach((page) => {
        page.classList.remove("active");
    });

    const target = document.getElementById(pageId);
    target.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });

    if (pageId === "page3") {
        renderDashboard();
        loadAlertHistory();
    }
}

function setMode(mode) {
    currentMode = mode;
    document.getElementById("crop-form").classList.toggle("hidden", mode !== "crop");
    document.getElementById("yield-form").classList.toggle("hidden", mode !== "yield");
    document.getElementById("tab-crop").classList.toggle("mode-tab-active", mode === "crop");
    document.getElementById("tab-yield").classList.toggle("mode-tab-active", mode === "yield");
    document.getElementById("form-description").textContent =
        mode === "crop"
            ? "Enter soil and climate values to get a crop recommendation from the trained model."
            : "Enter region, crop, and farm details to estimate total production in tonnes.";
    document.getElementById("submit-button").textContent =
        mode === "crop" ? "Recommend my crop →" : "Predict production →";
}

function getNumberValue(id) {
    const value = document.getElementById(id).value.trim();
    if (value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function getTextValue(id) {
    return document.getElementById(id).value.trim();
}

function setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value !== null && value !== undefined && value !== "") {
        input.value = value;
        input.classList.add("gps-filled");
    }
}

function showError(message) {
    alert(message);
}

function formatCurrency(value) {
    return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

async function bootstrapAuth() {
    const token = getAuthToken();
    if (!token) {
        updateAuthUi();
        showPage("page-login");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: authHeaders(),
        });
        if (!response.ok) throw new Error("Session expired");
        currentUser = await response.json();
        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(currentUser));
        updateAuthUi();
        showPage("page1");
    } catch {
        logout(false);
        showPage("page-login");
    }
}

async function sendOtp() {
    const phone = getTextValue("login-phone");
    if (phone.length !== 10) {
        showError("Enter a valid 10-digit mobile number.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/send-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not send OTP.");

        document.getElementById("login-step-phone").classList.add("hidden");
        document.getElementById("login-step-otp").classList.remove("hidden");
        document.getElementById("login-otp-hint").textContent =
            `OTP sent to ${data.phone}. Check your SMS inbox.`;

        const devHint = document.getElementById("login-dev-hint");
        if (data.dev_otp) {
            devHint.textContent = `Development mode OTP: ${data.dev_otp}`;
            devHint.classList.remove("hidden");
        } else {
            devHint.classList.add("hidden");
        }
    } catch (error) {
        showError(error.message);
    }
}

async function verifyOtp() {
    const phone = getTextValue("login-phone");
    const otp = getTextValue("login-otp");
    const name = getTextValue("login-name") || "Farmer";

    if (!otp || otp.length < 4) {
        showError("Enter the OTP sent to your phone.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/verify-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, otp, name }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "OTP verification failed.");

        localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(data.user));
        currentUser = data.user;
        updateAuthUi();
        resetLoginFlow();
        showPage("page1");
        maybePromptForLocation();
    } catch (error) {
        showError(error.message);
    }
}

function resetLoginFlow() {
    document.getElementById("login-step-phone").classList.remove("hidden");
    document.getElementById("login-step-otp").classList.add("hidden");
    document.getElementById("login-otp").value = "";
    document.getElementById("login-dev-hint").classList.add("hidden");
}

function logout(showLogin = true) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    currentUser = null;
    updateAuthUi();
    if (showLogin) showPage("page-login");
}

async function loadYieldOptions() {
    try {
        const response = await fetch(`${API_BASE}/options/yield`);
        if (!response.ok) return;
        const data = await response.json();
        fillDatalist("area-options", data.areas || []);
        fillDatalist("item-options", data.items || []);
    } catch (error) {
        console.warn("Could not load yield dropdown options:", error);
    }
}

async function loadCropPrices() {
    try {
        const response = await fetch(`${API_BASE}/options/prices`);
        if (!response.ok) return;
        const data = await response.json();
        cropPrices = data.prices_inr_per_tonne || {};
    } catch (error) {
        console.warn("Could not load crop prices:", error);
    }
}

function fillDatalist(listId, values) {
    const datalist = document.getElementById(listId);
    datalist.innerHTML = "";
    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        datalist.appendChild(option);
    });
}

function showLocationModal() {
    document.getElementById("gps-modal").classList.remove("hidden");
}

function dismissLocationModal() {
    document.getElementById("gps-modal").classList.add("hidden");
    localStorage.setItem(LOCATION_PROMPT_KEY, "dismissed");
}

function acceptLocationAccess() {
    dismissLocationModal();
    localStorage.setItem(LOCATION_PROMPT_KEY, "accepted");
    requestLocationAccess();
}

function requestLocationAccess() {
    if (!navigator.geolocation) {
        showError("GPS is not supported in this browser.");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            lastKnownCoords = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
            };
            fetchLocationContext(lastKnownCoords.latitude, lastKnownCoords.longitude);
        },
        (error) => {
            let message = "Could not access your location.";
            if (error.code === error.PERMISSION_DENIED) {
                message = "Location permission was denied. You can still enter values manually.";
            }
            showError(message);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 300000 }
    );
}

async function fetchLocationContext(latitude, longitude) {
    const status = document.getElementById("location-status");
    const label = document.getElementById("location-label");
    status.classList.remove("hidden");
    label.textContent = "Fetching weather and region data...";

    try {
        const response = await fetch(
            `${API_BASE}/location/context?latitude=${latitude}&longitude=${longitude}`
        );
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Location lookup failed.");

        locationContext = data;
        applyLocationContext(data);
        label.textContent = `${data.city ? `${data.city}, ` : ""}${data.region ? `${data.region}, ` : ""}${data.country}`;
    } catch (error) {
        label.textContent = "Could not load location details.";
        showError(error.message);
    }
}

function applyLocationContext(data) {
    if (data.temperature !== null) {
        setInputValue("crop-temperature", data.temperature);
        setInputValue("yield-temp", data.avg_temp ?? data.temperature);
    }
    if (data.humidity !== null) setInputValue("crop-humidity", data.humidity);
    if (data.annual_rainfall_mm !== null) setInputValue("yield-rainfall", data.annual_rainfall_mm);
    if (data.monthly_rainfall_mm !== null) setInputValue("crop-rainfall", data.monthly_rainfall_mm);
    if (data.matched_area) setInputValue("yield-area", data.matched_area);
    if (data.year) setInputValue("yield-year", data.year);
}

function guessCropPrice(cropName) {
    const normalized = (cropName || "").toLowerCase().trim();
    if (cropPrices[normalized]) return cropPrices[normalized];
    for (const [key, value] of Object.entries(cropPrices)) {
        if (normalized.includes(key) || key.includes(normalized)) return value;
    }
    return cropPrices.default || 25000;
}

async function submitPrediction() {
    if (currentMode === "crop") await predictCrop();
    else await predictYield();
}

async function predictCrop() {
    const payload = {
        N: getNumberValue("crop-n"),
        P: getNumberValue("crop-p"),
        K: getNumberValue("crop-k"),
        temperature: getNumberValue("crop-temperature"),
        humidity: getNumberValue("crop-humidity"),
        ph: getNumberValue("crop-ph"),
        rainfall: getNumberValue("crop-rainfall"),
    };

    if (Object.values(payload).some((value) => value === null)) {
        showError("Please fill in all soil and climate parameters.");
        return;
    }

    const button = document.getElementById("submit-button");
    button.disabled = true;
    button.textContent = "Predicting...";

    try {
        const response = await fetch(`${API_BASE}/predict/crop`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Crop prediction failed.");

        lastCropResult = { input: payload, result: data };
        lastRecommendedCrop = data.recommended_crop;
        lastYieldResult = null;
        lastYieldInput = null;
        showCropResults(payload, data);
        document.getElementById("save-dashboard-btn").classList.add("hidden");
        await loadPestInsights(data.recommended_crop);
        showPage("page2");
    } catch (error) {
        showError(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Recommend my crop →";
    }
}

async function predictYield() {
    const payload = {
        Area: getTextValue("yield-area"),
        Item: getTextValue("yield-item"),
        Year: getNumberValue("yield-year"),
        farm_area_ha: getNumberValue("yield-farm-area"),
        avg_temp: getNumberValue("yield-temp"),
        average_rain_fall_mm_per_year: getNumberValue("yield-rainfall"),
        pesticides_tonnes: getNumberValue("yield-pesticides"),
    };

    if (!payload.Area || !payload.Item || Object.values(payload).some((v) => v === null || v === "")) {
        showError("Please fill in all production prediction fields.");
        return;
    }

    const button = document.getElementById("submit-button");
    button.disabled = true;
    button.textContent = "Predicting...";

    try {
        const response = await fetch(`${API_BASE}/predict/yield`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Yield prediction failed.");

        setInputValue("yield-market-price", getNumberValue("yield-market-price") ?? guessCropPrice(payload.Item));
        lastYieldInput = payload;
        lastYieldResult = data;
        lastRecommendedCrop = payload.Item;
        lastCropResult = null;

        showYieldResults(payload, data);
        document.getElementById("save-dashboard-btn").classList.remove("hidden");
        await loadPestInsights(payload.Item);
        showPage("page2");
        await saveCurrentResultToDashboard(true);
    } catch (error) {
        showError(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Predict production →";
    }
}

async function loadPestInsights(crop) {
    const panel = document.getElementById("insights-panel");
    panel.classList.remove("hidden");

    try {
        const response = await fetch(`${API_BASE}/predict/pests?crop=${encodeURIComponent(crop)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Pest prediction failed.");

        document.getElementById("pest-season-label").textContent =
            `Current month: ${data.current_month} · ${data.current_season}`;

        const current = document.getElementById("pest-current-risks");
        current.innerHTML = "";
        (data.current_risks || []).forEach((item) => {
            current.innerHTML += `
                <div class="pest-card rounded-2xl p-4">
                    <div class="flex justify-between items-start gap-3 mb-2">
                        <span class="font-medium capitalize">${item.pest}</span>
                        <span class="risk-badge risk-${item.risk.toLowerCase()}">${item.risk} risk</span>
                    </div>
                    <p class="text-xs text-[hsl(215,25%,32%)] mb-1">${item.season} · ${item.months.join(", ")}</p>
                    <p class="text-sm">${item.advisory}</p>
                </div>`;
        });

        const calendar = document.getElementById("pest-seasonal-calendar");
        calendar.innerHTML = "";
        (data.seasonal_calendar || []).forEach((item) => {
            calendar.innerHTML += `
                <div class="border-b border-black/10 pb-3">
                    <div class="flex justify-between text-sm mb-1">
                        <span class="font-medium capitalize">${item.pest}</span>
                        <span class="text-[hsl(215,25%,32%)]">${item.season}</span>
                    </div>
                    <p class="text-xs text-[hsl(215,25%,32%)]">${item.months.join(", ")} · ${item.risk} risk</p>
                </div>`;
        });
    } catch (error) {
        document.getElementById("pest-season-label").textContent = error.message;
    }
}

async function enableEmergencyAlerts() {
    if (!isLoggedIn()) {
        showError("Login with your mobile number to receive SMS alerts.");
        showPage("page-login");
        return;
    }

    if (!lastRecommendedCrop) {
        showError("Run a crop or yield prediction first.");
        return;
    }

    const ensureCoords = () => new Promise((resolve, reject) => {
        if (lastKnownCoords) return resolve(lastKnownCoords);
        if (!navigator.geolocation) return reject(new Error("GPS unavailable."));
        navigator.geolocation.getCurrentPosition(
            (position) => {
                lastKnownCoords = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                };
                resolve(lastKnownCoords);
            },
            () => reject(new Error("GPS permission required for calamity alerts.")),
            { enableHighAccuracy: true, timeout: 15000 }
        );
    });

    const status = document.getElementById("alert-status-text");
    status.textContent = "Checking weather threats and registering alerts...";

    try {
        const coords = await ensureCoords();
        const response = await fetch(`${API_BASE}/alerts/check`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                crop: lastRecommendedCrop,
                latitude: coords.latitude,
                longitude: coords.longitude,
            }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Alert setup failed.");

        status.textContent = data.sms_sent
            ? "Emergency SMS sent to your mobile for an approaching calamity."
            : "Alerts enabled. No high-severity calamity detected right now.";
        loadAlertHistory();
    } catch (error) {
        status.textContent = error.message;
    }
}

async function loadAlertHistory() {
    const container = document.getElementById("alert-history-list");
    if (!isLoggedIn()) {
        container.innerHTML = '<p class="text-[hsl(215,25%,32%)]">Login to view SMS alert history.</p>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/alerts/history`, {
            headers: authHeaders(),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail);

        if (!data.alerts.length) {
            container.innerHTML = '<p class="text-[hsl(215,25%,32%)]">No emergency SMS alerts sent yet.</p>';
            return;
        }

        container.innerHTML = "";
        data.alerts.forEach((alert) => {
            container.innerHTML += `
                <div class="border-b border-black/10 pb-3">
                    <p class="font-medium capitalize">${alert.alert_type.replace("_", " ")}</p>
                    <p class="text-[hsl(215,25%,32%)] mt-1">${alert.message}</p>
                    <p class="text-xs mt-2">${new Date(alert.sent_at).toLocaleString("en-IN")}</p>
                </div>`;
        });
    } catch {
        container.innerHTML = '<p class="text-[hsl(215,25%,32%)]">Could not load alert history.</p>';
    }
}

function setSummaryLabels(labels) {
    ["summaryLabel1", "summaryLabel2", "summaryLabel3", "summaryLabel4", "summaryLabel5", "summaryLabel6", "summaryExtraLabel"]
        .forEach((id, index) => {
            document.getElementById(id).textContent = labels[index];
        });
}

function showCropResults(input, result) {
    document.getElementById("result-mode-label").textContent = "Crop recommendation";
    document.getElementById("result-title").innerHTML = 'Your field\'s <em class="not-italic">best crop.</em>';
    document.getElementById("crop-result-block").classList.remove("hidden");
    document.getElementById("yield-result-block").classList.add("hidden");
    document.getElementById("confidence-block").classList.remove("hidden");
    document.getElementById("cropResult").textContent = result.recommended_crop;
    document.getElementById("cropDescription").textContent =
        "Based on your soil and climate inputs, this crop is the model's top recommendation.";

    setSummaryLabels(["Temperature", "Humidity", "Nitrogen", "Phosphorus", "Potassium", "pH", "Rainfall"]);

    const confidenceList = document.getElementById("confidenceList");
    confidenceList.innerHTML = "";
    (result.top_predictions || []).forEach((item) => {
        confidenceList.innerHTML += `<div class="flex justify-between text-sm"><span class="capitalize">${item.crop}</span><span class="font-medium">${item.confidence}%</span></div>`;
    });

    document.getElementById("summaryArea").textContent = `${input.temperature} °C`;
    document.getElementById("summaryItem").textContent = `${input.humidity}% humidity`;
    document.getElementById("summaryN").textContent = input.N;
    document.getElementById("summaryP").textContent = input.P;
    document.getElementById("summaryK").textContent = input.K;
    document.getElementById("summaryPH").textContent = input.ph;
    document.getElementById("summaryExtra").textContent = `${input.rainfall} mm`;
}

function showYieldResults(input, result) {
    document.getElementById("result-mode-label").textContent = "Production prediction";
    document.getElementById("result-title").innerHTML = 'Your field\'s <em class="not-italic">potential.</em>';
    document.getElementById("crop-result-block").classList.add("hidden");
    document.getElementById("yield-result-block").classList.remove("hidden");
    document.getElementById("confidence-block").classList.add("hidden");
    document.getElementById("yieldResult").textContent = result.predicted_total_tonnes;
    document.getElementById("yieldPerHa").textContent = result.predicted_hg_ha_yield;

    setSummaryLabels(["Farm area", "Crop", "Region", "Year", "Temperature", "Pesticides", "Rainfall"]);
    document.getElementById("summaryArea").textContent = `${input.farm_area_ha} ha`;
    document.getElementById("summaryItem").textContent = input.Item;
    document.getElementById("summaryN").textContent = input.Area;
    document.getElementById("summaryP").textContent = input.Year;
    document.getElementById("summaryK").textContent = `${input.avg_temp} °C`;
    document.getElementById("summaryPH").textContent = `${input.pesticides_tonnes} t pesticides`;
    document.getElementById("summaryExtra").textContent = `${input.average_rain_fall_mm_per_year} mm/yr`;
}

async function calculateProfitSummary(input, result) {
    const farmArea = input.farm_area_ha;
    const pesticideSpend = getNumberValue("yield-pesticide-spend") ?? farmArea * 4500;

    const payload = {
        crop: input.Item,
        predicted_tonnes: result.predicted_total_tonnes,
        market_price_per_tonne: getNumberValue("yield-market-price") ?? guessCropPrice(input.Item),
        farm_area_ha: farmArea,
        pesticide_spend: pesticideSpend,
        seed_cost: getNumberValue("yield-seed-cost") ?? 0,
        labor_cost: getNumberValue("yield-labor-cost") ?? 0,
        fertilizer_cost: getNumberValue("yield-fertilizer-cost") ?? 0,
        region: input.Area,
    };

    const response = await fetch(`${API_BASE}/dashboard/profit`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Profit calculation failed.");
    return { payload, profit: data };
}

async function saveCurrentResultToDashboard(silent = false) {
    if (!lastYieldResult || !lastYieldInput) {
        if (!silent) showError("Save a production prediction first.");
        return;
    }

    try {
        const { payload, profit } = await calculateProfitSummary(lastYieldInput, lastYieldResult);
        const response = await fetch(`${API_BASE}/dashboard/records`, {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                crop: payload.crop,
                region: payload.region,
                production_tonnes: lastYieldResult.predicted_total_tonnes,
                revenue: profit.revenue,
                costs: profit.total_costs,
                profit: profit.net_profit,
                margin: profit.margin_percent,
                data_json: { breakdown: profit.breakdown, currency: "INR" },
            }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not save record.");
        if (!silent) showPage("page3");
    } catch (error) {
        if (!silent) showError(error.message);
    }
}

async function clearDashboardRecords() {
    if (!confirm("Clear all dashboard records?")) return;
    try {
        const response = await fetch(`${API_BASE}/dashboard/records`, {
            method: "DELETE",
            headers: authHeaders(),
        });
        if (!response.ok) throw new Error("Could not clear records.");
        renderDashboard();
    } catch (error) {
        showError(error.message);
    }
}

async function renderDashboard() {
    if (!isLoggedIn()) {
        showPage("page-login");
        return;
    }

    let records = [];
    try {
        const response = await fetch(`${API_BASE}/dashboard/records`, {
            headers: authHeaders(),
        });
        const data = await response.json();
        if (response.ok) records = data.records || [];
    } catch {
        records = [];
    }

    const totalRevenue = records.reduce((sum, item) => sum + item.revenue, 0);
    const totalCosts = records.reduce((sum, item) => sum + item.costs, 0);
    const netProfit = records.reduce((sum, item) => sum + item.profit, 0);
    const avgMargin = records.length
        ? records.reduce((sum, item) => sum + item.margin, 0) / records.length
        : 0;

    document.getElementById("dash-total-revenue").textContent = formatCurrency(totalRevenue);
    document.getElementById("dash-total-costs").textContent = formatCurrency(totalCosts);

    const netProfitEl = document.getElementById("dash-net-profit");
    netProfitEl.textContent = formatCurrency(netProfit);
    netProfitEl.classList.toggle("profit-positive", netProfit >= 0);
    netProfitEl.classList.toggle("profit-negative", netProfit < 0);

    document.getElementById("dash-avg-margin").textContent = formatPercent(avgMargin);
    document.getElementById("dash-record-count").textContent = String(records.length);
    document.getElementById("dash-last-updated").textContent = records[0]
        ? new Date(records[0].created_at).toLocaleString("en-IN")
        : "—";

    const bestRecord = [...records].sort((a, b) => b.profit - a.profit)[0];
    const topProduction = [...records].sort((a, b) => b.production_tonnes - a.production_tonnes)[0];

    document.getElementById("dash-best-crop").textContent = bestRecord ? bestRecord.crop : "—";
    document.getElementById("dash-top-production").textContent = topProduction
        ? `${topProduction.production_tonnes} t`
        : "—";

    renderProfitChart(records);
    renderDashboardTable(records);
}

function renderProfitChart(records) {
    const chart = document.getElementById("profit-chart");
    chart.innerHTML = "";
    if (!records.length) {
        chart.innerHTML = '<p class="text-sm text-[hsl(215,25%,32%)]">No profit data yet.</p>';
        return;
    }

    const grouped = {};
    records.forEach((record) => {
        grouped[record.crop] = (grouped[record.crop] || 0) + record.profit;
    });

    const entries = Object.entries(grouped).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const maxValue = Math.max(...entries.map(([, value]) => Math.abs(value)), 1);

    entries.forEach(([crop, profit]) => {
        const width = Math.max(8, (Math.abs(profit) / maxValue) * 100);
        chart.innerHTML += `
            <div>
                <div class="flex justify-between text-sm mb-2 capitalize">
                    <span>${crop}</span>
                    <span class="${profit >= 0 ? "profit-positive" : "profit-negative"} font-medium">${formatCurrency(profit)}</span>
                </div>
                <div class="chart-track">
                    <div class="chart-bar ${profit >= 0 ? "chart-bar-positive" : "chart-bar-negative"}" style="width:${width}%"></div>
                </div>
            </div>`;
    });
}

function renderDashboardTable(records) {
    const body = document.getElementById("dashboard-table-body");
    body.innerHTML = "";

    if (!records.length) {
        body.innerHTML = `<tr><td colspan="8" class="text-center text-[hsl(215,25%,32%)] py-8">No records yet. Run a production prediction to track profit in INR.</td></tr>`;
        return;
    }

    records.forEach((record) => {
        body.innerHTML += `
            <tr>
                <td>${new Date(record.created_at).toLocaleDateString("en-IN")}</td>
                <td class="capitalize">${record.crop}</td>
                <td>${record.region || "—"}</td>
                <td>${record.production_tonnes} t</td>
                <td>${formatCurrency(record.revenue)}</td>
                <td>${formatCurrency(record.costs)}</td>
                <td class="${record.profit >= 0 ? "profit-positive" : "profit-negative"} font-medium">${formatCurrency(record.profit)}</td>
                <td>${formatPercent(record.margin)}</td>
            </tr>`;
    });
}

function maybePromptForLocation() {
    if (localStorage.getItem(LOCATION_PROMPT_KEY)) return;
    showLocationModal();
}

document.addEventListener("DOMContentLoaded", async () => {
    setMode("crop");
    await loadYieldOptions();
    await loadCropPrices();
    await bootstrapAuth();
    if (isLoggedIn()) {
        maybePromptForLocation();
    }
});
