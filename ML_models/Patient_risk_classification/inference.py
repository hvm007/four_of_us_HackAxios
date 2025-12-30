import pandas as pd
import requests

def compute_abnormal_vitals_count(patient):
    abnormal = 0
    abnormal += int(patient['heartrate'] < 50 or patient['heartrate'] > 110)
    abnormal += int(patient['sbp'] < 90 or patient['sbp'] > 160)
    abnormal += int(patient['resprate'] < 12 or patient['resprate'] > 20)
    abnormal += int(patient['o2sat'] < 95)
    abnormal += int(patient['temperature'] < 36.0 or patient['temperature'] > 38.0)
    return abnormal


def ml_risk_band(probability):
    """
    Convert ML probability into baseline clinical risk band
    (semantic, not binary).
    """

    if probability < 0.45:
        return 'LOW'
    elif probability < 0.65:
        return 'MODERATE'
    elif probability < 0.85:
        return 'HIGH'
    else:
        return 'CRITICAL'

def escalate_risk(base_category, clinical_adjustment):
    """
    Escalate risk category based on rule severity.
    Rules can only increase risk, never decrease it.
    """

    levels = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']
    idx = levels.index(base_category)

    if clinical_adjustment >= 40:
        idx += 2
    elif clinical_adjustment >= 20:
        idx += 1

    return levels[min(idx, 3)]

def collapse_to_three_levels(final_category):
    """
    Collapse internal risk categories into 3 external categories
    """
    if final_category in ['HIGH', 'CRITICAL']:
        return 'HIGH'
    elif final_category == 'MODERATE':
        return 'MODERATE'
    else:
        return 'LOW'

# RISK SCORE CALCULATION
def calculate_risk_score(probability, patient):
    """
    Convert model probability + clinical rules into final decision
    """

    ml_score = probability * 100
    clinical_adjustment = 0
    reasons = []

    # --- RULES (unchanged logic) ---
    if patient['o2sat'] < 88:
        clinical_adjustment += 20
        reasons.append("Critical hypoxemia (SpO₂ < 88%)")
    elif patient['o2sat'] < 92:
        clinical_adjustment += 10
        reasons.append("Low oxygen saturation")

    if patient['sbp'] < 90:
        clinical_adjustment += 15
        reasons.append("Hypotension (SBP < 90)")

    if patient['resprate'] > 24:
        clinical_adjustment += 10
        reasons.append("Tachypnea (RR > 24)")

    if patient['heartrate'] > 120:
        clinical_adjustment += 10
        reasons.append("Tachycardia (HR > 120)")
    elif patient['heartrate'] < 40:
        clinical_adjustment += 10
        reasons.append("Bradycardia (HR < 50)")

    if patient['acuity'] >= 4:
        clinical_adjustment += 15
        reasons.append("Critical acuity (Level 4)")
    elif patient['acuity'] >= 3:
        clinical_adjustment += 10
        reasons.append("High acuity (Level 3)")
    elif patient['acuity'] >= 2:
        clinical_adjustment += 5
        reasons.append("Moderate acuity (Level 2)")

    if patient['arrival_ambulance'] == 1:
        clinical_adjustment += 5
        reasons.append("Arrived by ambulance")

    # --- FINAL DECISION LOGIC ---
    base_category = ml_risk_band(probability)
    final_category = escalate_risk(base_category, clinical_adjustment)

    final_score = min(ml_score + clinical_adjustment, 100)

    return {
        "risk_score": round(final_score, 1),
        "risk_category": final_category,
        "ml_probability": round(probability, 3),
        "ml_score": round(ml_score, 1),
        "clinical_adjustment": round(clinical_adjustment, 1),
        "contributing_factors": reasons
    }

def predict_patient_risk(patient, model, scaler, feature_names):
    patient = patient.copy()

    patient['abnormal_vitals_count'] = compute_abnormal_vitals_count(patient)

    df = pd.DataFrame([patient])[feature_names]
    scaled = scaler.transform(df)

    prob = model.predict_proba(scaled)[0][1]

    result = calculate_risk_score(prob, patient)
    result['final_triage_category'] = collapse_to_three_levels(
        result['risk_category']
    )
    result['ml_probability'] = round(prob, 3)

    return result


def generate_explanation(result, patient_vitals, groq_api_key=None):
    if groq_api_key is None:
        return None

    vitals_str = f"""
Heart Rate: {patient_vitals['heartrate']} bpm
Blood Pressure: {patient_vitals['sbp']}/{patient_vitals['dbp']} mmHg
Oxygen Saturation: {patient_vitals['o2sat']}%
Respiratory Rate: {patient_vitals['resprate']} /min
Temperature: {patient_vitals['temperature']} °C
Acuity Level: {patient_vitals['acuity']}
Arrival Mode: {"Ambulance" if patient_vitals['arrival_ambulance'] else "Walk-in"}
"""

    factors_str = (
        "\n".join(f"• {f}" for f in result["contributing_factors"])
        if result["contributing_factors"]
        else "No critical rule-based factors triggered."
    )

    prompt = f"""
You are a clinical AI assistant. Generate a brief explanation for hospital staff.

PATIENT ASSESSMENT:
Risk Score: {result['risk_score']}/100
Risk Category: {result['final_triage_category']}
ML Probability: {result['ml_probability']}

VITAL SIGNS:
{vitals_str}

CONTRIBUTING FACTORS:
{factors_str}

Write 2–3 sentences explaining why this patient was classified as
{result['final_triage_category']} risk.

Rules:
- Do NOT add new medical facts
- Do NOT diagnose or suggest treatment
- Do NOT contradict the risk category
- Use calm, factual language
"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 150,
        },
        timeout=10,
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
