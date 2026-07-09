import os
import json
import google.generativeai as genai

class StudyGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        
    def generate_syllabus(self, convocatoria_text: str) -> str:
        """
        Llama a la API (OpenAI/Gemini/Anthropic) para generar un índice del temario.
        """
        if not self.api_key:
            return "No LLM API Key configured. Please configure GEMINI_API_KEY to use the Study Module."
            
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Eres un experto preparador de oposiciones. Genera un índice de temario estructurado para esta convocatoria basada en su texto: {convocatoria_text[:2000]}. Devuélvelo en formato Markdown limpio."
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error llamando a Gemini: {str(e)}"

    def generate_case_study(self, tema: str) -> str:
        """
        Genera un supuesto práctico para un tema específico.
        """
        if not self.api_key:
            return "No LLM API Key configured."
            
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Eres un tribunal de oposiciones de la administración pública. Escribe un supuesto práctico realista sobre el tema: {tema}."
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"
        
    def generate_test(self, convocatoria_text: str) -> str:
        """
        Genera un test rápido interactivo (5 preguntas) basado en el temario.
        Devuelve un JSON string con la estructura de preguntas y respuestas.
        """
        if not self.api_key:
            return json.dumps({"error": "No LLM API Key configured (Set GEMINI_API_KEY)"})

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            Eres un experto preparador de oposiciones.
            Crea un test de 5 preguntas de opción múltiple basándote en la siguiente convocatoria:
            {convocatoria_text[:1500]}
            
            Devuelve ÚNICAMENTE un JSON válido con esta estructura estricta:
            {{
                "test": [
                    {{
                        "question": "Pregunta 1?",
                        "options": ["a", "b", "c", "d"],
                        "correct_index": 0
                    }}
                ]
            }}
            No incluyas markdown como ```json o texto adicional.
            """
            response = model.generate_content(prompt)
            text = response.text.replace("```json", "").replace("```", "").strip()
            return text
        except Exception as e:
            return json.dumps({"error": f"Error llamando a Gemini: {str(e)}"})
