# Google AI Studio / Gemini TTS Pay-As-You-Go Billing Setup Guide

> **Project:** Sutradhar Hindi-Only Voice Engine  
> **Target Service:** Google AI Studio / Gemini API (`generativelanguage.googleapis.com`)  
> **Strict Spending Limit:** ₹5.00 INR Maximum  
> **Status:** User Action Required (Follow this guide to activate billing safely)  
> **Authoritative Official References:**
> - [Google AI Studio Documentation](https://ai.google.dev/docs)
> - [Gemini API Pricing Page](https://ai.google.dev/pricing)
> - [Google AI Studio Billing Setup Guide](https://ai.google.dev/gemini-api/docs/billing)
> - [Google Cloud Quota Management](https://cloud.google.com/docs/quota/manage-quota)
> - [Google Cloud Budgets & Spend Caps](https://cloud.google.com/billing/docs/how-to/budgets)
> - [Google Cloud Billing India Payment Methods](https://cloud.google.com/billing/docs/how-to/payment-methods#india)

---

## Executive Summary

To produce daily Sutradhar YouTube Shorts (each requiring 6–8 audio generation calls across multiple scenes), the Google AI Studio Free Tier limit of **10 requests per day (RPD)** is insufficient. Upgrading to the **Pay-As-You-Go (Paid Tier)** removes the daily request cap and raises rate limits to over 1,000 requests per minute (RPM).

Because Gemini TTS output is priced at **$0.50 per 1 million characters** (~$0.0000005 per character):
- A full 60-second Hindi Short (~550 Devanagari characters) costs approximately **₹0.0236 INR** (~2.4 paise).
- With 18% Indian GST, the total cost per Short is approximately **₹0.0279 INR** (~2.8 paise).
- A **₹5.00 INR budget provides capacity for approximately 179 full YouTube Shorts**.
- A full month of daily Shorts (30 episodes) costs less than **₹0.85 INR**.

However, **Google Cloud budgets do NOT halt API traffic by default**, and usage telemetry can experience reporting delays. To guarantee that charges **never exceed ₹5.00**, this guide implements a **4-layer safety shield**, anchored by a real-time **API Request Quota Cap** that blocks requests at the gateway level with 0ms delay.

---

## 1. The ₹5.00 Spending Limit: Reality, Limitations & Hard-Cap Enforcement

Before enabling billing, it is critical to understand how Google Cloud billing and enforcement mechanisms operate.

### The Limitations of Standard Controls

| Control Mechanism | How It Works | Can It Guarantee a Hard ₹5 Cap Alone? | Why or Why Not? |
| :--- | :--- | :---: | :--- |
| **Standard Budget Alerts** | Sends email when spend reaches 50%, 90%, 100% of ₹5. | ❌ **NO** | Google explicitly states that budget alerts are informational only. They do **not** shut down APIs or reject requests. |
| **Billing Telemetry Latency** | Cloud Billing data ingestion. | ❌ **NO** | Billing metrics are processed with a **12 to 24-hour reporting lag**. A runaway loop could execute hundreds of calls before the budget engine evaluates the spend. |
| **Native Spend Caps (GCP 2026)** | Pauses service requests when budget reaches 100%. | ⚠️ **PARTIAL** | While native spend caps now exist for Gemini API, enforcement still has a latency of several minutes. Overages during that window are billable. |
| **Indian Prepayment Rules** | RBI / Google India payment rails. | ⚠️ **CONDITIONAL** | If upgrading via AI Studio's direct Prepay UI, Google mandates an initial deposit of **$5.00 USD (~₹420–₹435 INR)**. If linking via Google Cloud Console postpaid billing with an Indian credit/debit card, a refundable ₹2 authorization is charged, with actual usage billed monthly. UPI setup typically mandates a ₹500 INR initial prepayment. |

---

### The True Hard Stop: API Request Quota Capping (0ms Gateway Enforcement)

The **only 100% foolproof mechanism** to enforce a sub-₹5 spending limit in real time is **Google Cloud API Quota Capping**:

```
[ Application / Sutradhar Engine ]
               │
               ▼
┌──────────────────────────────────────────────┐
│  Google Cloud API Gateway                    │
│  Quota Enforcement: Max 50 Requests / Day    │
└──────────────────────────────────────────────┘
         │                           │
  (Requests 1–50)              (Request 51+)
         │                           │
         ▼                           ▼
┌─────────────────┐        ┌───────────────────┐
│ Gemini TTS API  │        │ HTTP 429 REJECTED │
│ Cost: ₹0.00017  │        │ RESOURCE_EXHAUSTED│
└─────────────────┘        │ Cost: ₹0.000000   │
                           └───────────────────┘
```

1. **Where it runs:** At Google's edge API gateway, **before** the request reaches the Gemini model.
2. **Latency:** **0 milliseconds**. The 51st request on any day is instantly rejected with `HTTP 429 RESOURCE_EXHAUSTED`.
3. **Cost of rejected requests:** **₹0.00**. Rejected requests are never billed.
4. **The Math:**
   - Sutradhar needs ~8 requests per Short (6 scenes + 2 retries).
   - Setting a quota cap of **50 requests per day** allows up to 6 complete Shorts per day.
   - 50 requests $\times$ 90 chars $\approx$ 4,500 characters $\approx$ $0.00000225 USD $\approx$ **₹0.00019 INR per day**.
   - Maximum possible spend in a 30-day month: 30 $\times$ ₹0.00019 = **₹0.0058 INR (approx. half a paisa for the entire month)**.
   - Even in the absolute worst-case scenario where an infinite loop attempts 10,000,000 calls, only the first 50 succeed. The remaining 9,999,950 calls are rejected at zero cost.

---

## 2. Multi-Layer Safety Architecture (The 4-Layer Shield)

To ensure zero risk, complete service isolation, and strict cost control, we apply four interlocking layers:

```mermaid
flowchart TD
    subgraph L1 ["Layer 1: Project Isolation"]
        P["Dedicated GCP Project: 'sutradhar-tts-prod'"]
        P --> D["Zero other APIs enabled (No Compute, Storage, BigQuery)"]
    end

    subgraph L2 ["Layer 2: API Key Scope"]
        K["Gemini API Key"]
        K --> R["Restricted STRICTLY to 'Generative Language API'"]
    end

    subgraph L3 ["Layer 3: Gateway Real-Time Hard Stop"]
        Q["API Quotas & System Limits"]
        Q --> QC["Daily Cap: 50 requests/day (HTTP 429 on overflow)"]
    end

    subgraph L4 ["Layer 4: Financial Ceiling"]
        B["Cloud Billing Budget"]
        B --> BA["₹5.00 Target Amount + Spend Cap + Alerts at ₹2.50, ₹4.00, ₹5.00"]
    end

    L1 --> L2 --> L3 --> L4
```

1. **Layer 1: Project Isolation**  
   A brand-new, isolated Google Cloud Project containing **only** the Generative Language API. No Google Cloud Storage, Compute Engine, BigQuery, Vertex AI, or Cloud Functions can generate background charges.
2. **Layer 2: API Key Scoping**  
   The API key is locked with API restrictions so it can **only** authorize `generativelanguage.googleapis.com`. It will fail with `HTTP 403 Forbidden` if presented to any other Google Cloud service.
3. **Layer 3: Real-Time Quota Cap**  
   Daily generation requests are capped at 50 requests/day, mathematically constraining maximum monthly expenditure to under ₹0.01 INR.
4. **Layer 4: Financial Spend Cap & Alert Thresholds**  
   A budget of ₹5.00 INR is created with email alert triggers at ₹2.50 (50%), ₹4.00 (80%), and ₹5.00 (100%), with Native Spend Cap enabled if eligible.

---

## 3. Pricing Breakdown & Sutradhar Episode Economics

### Official Rate Card (Gemini API Paid Tier)

| Modality / Resource | Official Rate (USD) | Rate in INR (@ ₹86 / USD) |
| :--- | :--- | :--- |
| **Audio Output (TTS)** | **$0.50 per 1,000,000 characters** | **₹0.000043 per character** |
| **Text Input (Prompt)** | $0.075 per 1,000,000 tokens | ₹0.00000645 per token |
| **Context Caching** | Free (under threshold) | ₹0.00 |
| **Applicable Tax** | 18% Goods & Services Tax (GST) | Applied to all Indian billing accounts |

---

### Per-Short Production Cost Breakdown

For a standard Sutradhar YouTube Short:
- **Narration Characters:** ~550 Devanagari characters across 6 scenes.
- **API Request Count:** 6 scenes + 2 retry/variation calls = **8 API requests**.
- **Prompt Input Tokens:** ~1,200 tokens total across 8 requests.

$$\text{Audio Cost} = 550 \text{ chars} \times \$0.0000005 = \$0.000275 \text{ USD}$$
$$\text{Input Cost} = 1,200 \text{ tokens} \times \$0.000000075 = \$0.00000009 \text{ USD}$$
$$\text{Subtotal per Short} = \$0.00027509 \text{ USD} \approx \mathbf{₹0.02365 \text{ INR}} \text{ (2.36 paise)}$$
$$\text{Total with 18\% GST} = ₹0.02365 \times 1.18 = \mathbf{₹0.0279 \text{ INR}} \text{ (2.79 paise)}$$

---

### Monthly Projections vs. ₹5.00 Budget

| Volume | Audio Characters | Cost (USD) | Cost (INR excl. GST) | Cost (INR incl. 18% GST) | Budget Consumed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1 Short** | 550 chars | $0.000275 | ₹0.0236 | **₹0.0279** | 0.56% of ₹5 |
| **10 Shorts** | 5,500 chars | $0.002750 | ₹0.2365 | **₹0.2791** | 5.58% of ₹5 |
| **30 Shorts (1 Month)** | 16,500 chars | $0.008250 | ₹0.7095 | **₹0.8372** | **16.74% of ₹5** |
| **90 Shorts (1 Quarter)**| 49,500 chars | $0.024750 | ₹2.1285 | **₹2.5116** | 50.23% of ₹5 |
| **179 Shorts (Max Cap)** | 98,450 chars | $0.049225 | ₹4.2333 | **₹4.9950** | **99.90% of ₹5** |

> **Key Takeaway:** ₹5.00 INR is more than enough to fund **nearly 6 months of daily video generation** at our normal production cadence.

---

## 4. Step-by-Step Setup Instructions

Please complete the following steps in order.

### Step 1: Create a Dedicated, Isolated Google Cloud Project

Do not reuse an existing personal or corporate project. Creating a dedicated project guarantees no other resources share the billing account.

1. Open the [Google Cloud Console Resource Manager](https://console.cloud.google.com/cloud-resource-manager).
2. Click **Create Project** at the top.
3. Configure the project details:
   - **Project Name:** `sutradhar-tts-prod`
   - **Organization:** Select *No organization* (or your personal domain).
4. Note your unique **Project ID** (e.g., `sutradhar-tts-prod-123456`).
5. Click **Create** and wait for the confirmation notification.
6. In the top project selector dropdown, switch to your new project `sutradhar-tts-prod`.

---

### Step 2: Enable ONLY the Generative Language API

1. In the Google Cloud search bar at the top, type `Generative Language API` and press Enter.
   - Direct Link: [Generative Language API Page](https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com)
2. Ensure your project `sutradhar-tts-prod` is selected in the top bar.
3. Click **Enable**.
4. Confirm that **NO other APIs** (such as *Compute Engine API*, *Cloud Storage*, *Vertex AI API*, or *Cloud SQL*) are enabled.

---

### Step 3: Link or Set Up the Cloud Billing Account

Google Cloud accounts in India are serviced by **Google Cloud India Private Limited** in INR with 18% GST.

1. Navigate to [Google Cloud Console Billing](https://console.cloud.google.com/billing).
2. If you already have an active Google Cloud Billing account:
   - Select your billing account.
   - Go to **Account Management**.
   - Under *Projects linked to this billing account*, click **Link Project** and select `sutradhar-tts-prod`.
3. If you do not have a billing account:
   - Click **Manage Billing Accounts** > **Create Account**.
   - Select **India** as the country and **Indian Rupee (INR)** as the currency.
   - Under *Account Type*, select **Individual** (or Business if you have a GSTIN).
   - Enter your name and address.
   - **Payment Method:**
     - **Credit / Debit Card (Visa, MasterCard):** Recommended for Pay-As-You-Go. Google performs a small verification transaction (~₹2 INR) with an OTP to register the RBI e-mandate, which is immediately reversed. Usage is billed post-facto at month-end.
     - **UPI:** If choosing UPI, Google Cloud requires an initial prepayment deposit (usually ₹500 INR minimum). *If your intention is to strictly limit commitment to ₹5, use a credit/debit card on postpaid billing rather than UPI prepayment.*
4. Link this billing account to `sutradhar-tts-prod`.

---

### Step 4: Configure the ₹5.00 Spend Cap & Alert Thresholds

1. Go to **Billing** > **Budgets & alerts** in Google Cloud Console.
   - Direct Link: [Budgets & Alerts](https://console.cloud.google.com/billing/budgets)
2. Click **Create Budget**.
3. **Step 1: Scope:**
   - **Name:** `sutradhar-tts-strict-5inr-budget`
   - **Time range:** *Monthly*
   - **Projects:** Check **ONLY** `sutradhar-tts-prod` (uncheck all other projects).
   - **Services:** Select *All services* (or specifically *Generative Language API*).
   - Click **Next**.
4. **Step 2: Amount:**
   - **Budget type:** *Specified amount*
   - **Target amount:** `₹5.00`
   - Click **Next**.
5. **Step 3: Actions & Alert Thresholds:**
   - Set the following alert percentages:
     - **50% of budget** (`₹2.50`) — Trigger: Actual spend
     - **80% of budget** (`₹4.00`) — Trigger: Actual spend
     - **100% of budget** (`₹5.00`) — Trigger: Actual spend
   - Check **Email alerts to billing admins and users**.
   - If available on your account, enable **Spend Cap / Stop usage when budget is reached**.
   - Click **Finish**.

---

### Step 5: Enforce the Zero-Latency Hard Cap (API Request Quota)

This is the **mandatory step** that physically prevents charges exceeding ₹5.00 even if a software loop occurs.

1. Navigate to **IAM & Admin** > **Quotas & System Limits**.
   - Direct Link: [Cloud Console Quotas](https://console.cloud.google.com/iam-admin/quotas)
2. Ensure `sutradhar-tts-prod` is selected in the top project dropdown.
3. In the filter bar, enter:
   - `Service: Generative Language API`
   - `Metric: generativelanguage.googleapis.com/generate_content_requests`
4. Look for the quota row:
   - **Quota Name:** `GenerateContent request limit per day` (or `Requests per day`)
5. Check the box next to that quota and click **Edit Quotas** at the top right.
6. Set the **New Limit** to:
   $$\mathbf{50} \text{ requests per day}$$
   *(Note: 50 requests allows ~6 full Shorts per day while mathematically capping daily spend at ₹0.00019 INR).*
7. Also set **Requests per minute (RPM)** to:
   $$\mathbf{10} \text{ requests per minute}$$
8. Enter a brief description (e.g., `Sutradhar development cost ceiling`) and click **Submit Request** / **Done**.
9. The quota takes effect immediately across Google's edge proxies.

---

### Step 6: Create and Lock Down the Gemini API Key

1. Go to **APIs & Services** > **Credentials**.
   - Direct Link: [Credentials Page](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials** > **API Key**.
3. A modal will display your new API key. **Do not close it yet.** Click **Edit API Key** (or click the pencil icon next to the key).
4. Configure Key Restrictions:
   - **Name:** `sutradhar-gemini-tts-key`
   - **Set Application Restrictions:**
     - For local development, leave as *None* or restrict to your specific static IP address if you have one.
   - **Set API Restrictions (CRITICAL):**
     - Select **Restrict key**.
     - In the dropdown, find and select **ONLY** `Generative Language API`.
     - Confirm that no other APIs are checked.
5. Click **Save**.

---

### Step 7: Update Sutradhar Local Configuration

Once your locked-down API key is generated:

1. Open `.env` in the Sutradhar project root.
2. Update the `GEMINI_API_KEY` entry:
   ```env
   GEMINI_API_KEY=AIzaSyYourGeneratedAndRestrictedKeyHere
   ```
3. Save the file.
4. **Safety Check:** Confirm that `.env.local.example` has **not** been modified.
5. Run the existing test suite to ensure the environment configuration loads cleanly:
   ```bash
   pytest tests/
   ```

---

## 5. Monitoring Usage & Cost Verification

After configuring billing and generating audio, you can verify your expenditure in real time using the following tools:

### 1. Google Cloud Billing Reports
- Navigate to [Billing > Reports](https://console.cloud.google.com/billing/reports).
- Group by: **Service** and **SKU**.
- Time range: **This month**.
- Confirm that charges are accruing exclusively under `Generative Language API` and remain in fractions of a rupee.

### 2. Google AI Studio Spend Dashboard
- Open [Google AI Studio](https://aistudio.google.com/).
- Click **Settings** (gear icon) > **Billing**.
- Review current token consumption, request counts, and estimated cost.

### 3. API Quota Dashboard
- Open [APIs & Services > Dashboard](https://console.cloud.google.com/apis/dashboard).
- Click **Generative Language API** to see your live traffic graphs, request volume, and confirm you remain comfortably below the 50 RPD limit.

---

## 6. Verification Checklist Before First Production Call

Before authorizing the first character voice synthesis run, verify that every item on this checklist is complete:

- [ ] Dedicated project `sutradhar-tts-prod` created and active.
- [ ] Only `generativelanguage.googleapis.com` is enabled in APIs & Services.
- [ ] Billing account linked with INR currency and 18% GST profile.
- [ ] Monthly budget created with target amount `₹5.00` and alerts set at 50%, 80%, 100%.
- [ ] API quota for `GenerateContent requests per day` explicitly capped at **50 requests/day**.
- [ ] Gemini API key created with API restriction set strictly to **Generative Language API**.
- [ ] Key updated in `.env` (and never committed to Git).
- [ ] `.env.local.example` remains 100% intact and untouched.

---

## 7. Next Steps: Character Voice Roster Audition

Once you have completed the steps above and configured billing on your Google Cloud project:

1. Notify the assistant that billing and quotas are configured.
2. The assistant will run the calibrated Gemini TTS audition script to synthesize audio for our finalized character roster:
   - **Sutradhar / Mahadev:** Voice `Charon` + Sutradhar Narrator DSP (calibrated 99.5% match to Viraj).
   - **Ravana:** Voice `Puck` + Antagonist DSP (calibrated to Niraj).
   - **Mandodari:** Voice `Kore` + Expressive Female DSP (calibrated acoustic twin to Kanika).
   - **Supporting Characters:** Tested across `Fenrir`, `Aoede`, and `Leda`.
3. Side-by-side listening comparison will be compiled for your final sign-off.
