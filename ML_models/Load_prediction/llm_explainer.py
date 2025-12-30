import json
import requests
from datetime import datetime

# GROQ API INTEGRATION

class LLMExplainer:
    """
    Converts model predictions to clinical explanations using Groq LLM
    """
    
    def __init__(self, api_key):
        """
        Initialize Groq LLM explainer
        
        Args:
            api_key: Groq API key (required - get from https://console.groq.com)
        """
        if not api_key:
            raise ValueError("Groq API key is required! Get one from https://console.groq.com")
        
        self.api_key = api_key
        self.endpoint = 'https://api.groq.com/openai/v1/chat/completions'
        self.model = 'llama-3.3-70b-versatile'
    
    def explain_prediction(self, prediction_data, historical_context=None):
        """
        Generate clinical explanation for prediction using Groq
        
        Args:
            prediction_data: Dict from predict_next_hour_enhanced()
            historical_context: Optional recent trends/patterns
            
        Returns:
            Dict with explanation and metadata
        """
        
        # Build prompt
        prompt = self._build_explanation_prompt(prediction_data, historical_context)
        
        # Call Groq API
        response = self._call_groq(prompt)
        
        return response
    
    def _build_explanation_prompt(self, prediction_data, historical_context):
        """
        Create structured prompt for Groq LLM
        """
        
        pred = prediction_data.copy()
        pred['predicted_arrivals'] = int(pred['predicted_arrivals'])
        pred['lower_bound'] = int(round(pred['lower_bound']))
        pred['upper_bound'] = int(round(pred['upper_bound']))
        
        reasoning = pred.get('reasoning', {})
        
        # Format timestamp
        timestamp = pred['timestamp']
        time_str = timestamp.strftime('%I:%M %p')
        day_str = timestamp.strftime('%A, %B %d')
        
        prompt = f"""You are an ER operations advisor. Explain this forecast to hospital staff in clear, actionable language.

PREDICTION SUMMARY:
- Time: {time_str} on {day_str}
- Expected arrivals: {pred['predicted_arrivals']} patients
- Expected range: {pred['lower_bound']} to {pred['upper_bound']} patients
- Confidence level: {pred['confidence_level'].upper()}

CONTEXT:
- Hour of day: {reasoning.get('hour', 'N/A')}
- Night time: {'Yes' if reasoning.get('is_night') else 'No'}
- Evening rush: {'Yes' if reasoning.get('is_evening_rush') else 'No'}
- Recent trend: {reasoning.get('recent_trend', 'stable')}
- High load recently: {'Yes' if reasoning.get('high_load_recent') else 'No'}

INSTRUCTIONS:
1. Provide a concise 2-3 sentence explanation of WHY we expect this arrival rate
2. Give ONE specific, actionable recommendation for ER staff
3. Flag any concerns if confidence is LOW or surge is predicted
4. Use simple language - avoid jargon
5. Be direct and practical

Keep response under 150 words. Structure as:
FORECAST: [brief explanation]
RECOMMENDATION: [one clear action]
[ALERT if needed]

Do not include any preamble, just provide the structured response."""

        if historical_context:
            prompt += f"\n\nRECENT PATTERNS:\n{historical_context}"
        
        return prompt
    
    def _call_groq(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
        payload = {
        "model": self.model,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert ER operations advisor. Be concise and practical."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }

    
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
    
        # 🔍 Debug if it fails again
        if response.status_code != 200:
            raise Exception(
                f"Groq API Error {response.status_code}: {response.text}"
            )
    
        result = response.json()
    
        return {
            "explanation": result["choices"][0]["message"]["content"].strip(),
        }



