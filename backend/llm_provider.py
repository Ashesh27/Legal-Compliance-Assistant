import os
import ollama
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class LLMProvider:
    """
    Classe base per gestire diversi provider LLM.
    """
    
    def __init__(self, provider: str = None):
        """
        Inizializza il provider LLM.
        
        Args:
            provider: Nome del provider (ollama, gemini, openai, etc.)
                      Se None, usa la variabile d'ambiente LLM_PROVIDER
        """
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")
        self.api_key = None
        self.gemini = None
        self.openai_client = None
        
        # Inizializza il client in base al provider
        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "ollama":
            pass  # Ollama non richiede inizializzazione speciale
        else:
            raise ValueError(f"Provider non supportato: {self.provider}")
    
    def _init_gemini(self):
        """Inizializza il client Gemini."""
        try:
            import google.generativeai as genai
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY non trovata nelle variabili d'ambiente")
            genai.configure(api_key=self.api_key)
            self.gemini = genai
            print("Provider Gemini inizializzato")
        except ImportError:
            raise ImportError("Installa google-generativeai: pip install google-generativeai")
    
    def _init_openai(self):
        """Inizializza il client OpenAI."""
        try:
            from openai import OpenAI
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY non trovata nelle variabili d'ambiente")
            self.openai_client = OpenAI(api_key=self.api_key)
            print("Provider OpenAI inizializzato")
        except ImportError:
            raise ImportError("Installa openai: pip install openai")
    
    def chat(self, model: str, messages: list, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Invia una richiesta al provider LLM.
        
        Args:
            model: Nome del modello da utilizzare (es. 'gemini-1.5-pro')
            messages: Lista di messaggi (formato standard con role/content)
            options: Opzioni aggiuntive (temperature, max_tokens, etc.)
        
        Returns:
            Dizionario con la risposta nel formato standardizzato
        """
        if options is None:
            options = {}
        
        if self.provider == "ollama":
            return self._chat_ollama(model, messages, options)
        elif self.provider == "gemini":
            return self._chat_gemini(model, messages, options)
        elif self.provider == "openai":
            return self._chat_openai(model, messages, options)
    
    def _chat_ollama(self, model: str, messages: list, options: Dict[str, Any]) -> Dict[str, Any]:
        """Chat con Ollama."""
        response = ollama.chat(
            model=model,
            messages=messages,
            options=options
        )
        return response
    
    def _chat_gemini(self, model: str, messages: list, options: Dict[str, Any]) -> Dict[str, Any]:
        """Chat con Gemini (Ottimizzata per documenti e Safety Filters disattivati)."""
        
        # Importiamo i tipi necessari per la configurazione robusta
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        
        # 1. Configurazione Safety Settings: BLOCK_NONE su tutto per evitare falsi positivi su documenti "risk/compliance"
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Estrai system prompt se presente
        system_instruction = None
        user_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_instruction = msg['content']
            else:
                user_messages.append(msg)
        
        # Configura il modello
        # Nota: Assicurarsi di passare un modello 1.5 (es. gemini-1.5-pro) nella chiamata
        gemini_model = self.gemini.GenerativeModel(
            model,
            system_instruction=system_instruction,
            safety_settings=safety_settings
        )
        
        # 2. Configura i parametri di generazione con token aumentati
        # Usiamo l'oggetto GenerationConfig per maggiore stabilità
        generation_config = self.gemini.types.GenerationConfig(
            temperature=options.get('temperature', 0.1),
            max_output_tokens=options.get('num_predict', 100000), # Aumentato drasticamente su richiesta utente per chunk grandi
            top_p=options.get('top_p', 0.95),
        )
        
        # Converti i messaggi rimanenti in formato Gemini
        chat_history = []
        for i, msg in enumerate(user_messages[:-1]):
            role = "user" if msg['role'] == 'user' else "model"
            chat_history.append({
                'role': role,
                'parts': [msg['content']]
            })
        
        # Ultimo messaggio è la query corrente
        current_message = user_messages[-1]['content'] if user_messages else ""
        
        try:
            # Invia la richiesta
            if chat_history:
                chat = gemini_model.start_chat(history=chat_history)
                response = chat.send_message(
                    current_message,
                    generation_config=generation_config
                )
            else:
                response = gemini_model.generate_content(
                    current_message,
                    generation_config=generation_config
                )
            
            # Verifica base candidati
            if not response.candidates:
                if response.prompt_feedback:
                     raise ValueError(f"Prompt bloccato dai filtri di input: {response.prompt_feedback}")
                raise ValueError("Gemini non ha restituito candidati (errore generico API).")
            
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            print(f"DEBUG: Gemini finish_reason: {finish_reason}")
            
            if candidate.content and candidate.content.parts:
                 print(f"DEBUG: Gemini parts count: {len(candidate.content.parts)}")
            else:
                 print("DEBUG: Gemini parts is empty")
            
            # 3. Verifica Finish Reason più permissiva
            # 1 = STOP (Finito correttamente)
            # 2 = MAX_TOKENS (Finito perché ha raggiunto il limite token - accettabile)
            if finish_reason not in [1, 2]:
                error_msg = f"Gemini blocked response - finish_reason: {finish_reason}"
                if hasattr(candidate, 'safety_ratings'):
                    error_msg += f"\nSafety ratings: {[(r.category, r.probability) for r in candidate.safety_ratings]}"
                raise ValueError(error_msg)
            
            # Estrazione sicura del testo
            content_text = ""
            if candidate.content and candidate.content.parts:
                content_text = candidate.content.parts[0].text
            elif finish_reason == 2:
                # Se troncato per max tokens e nessuna parte valida, ritorna stringa vuota o parziale se disponibile
                # In alcuni casi response.text fallisce se parts è vuoto
                content_text = ""
            else:
                # Prova comunque response.text che potrebbe avere logica interna o fallire con errore descrittivo
                content_text = response.text

            return {
                "message": {
                    "role": "assistant",
                    "content": content_text
                }
            }
            
        except Exception as e:
            # Rilanciamo l'errore mantenendo il contesto
            raise ValueError(f"Errore durante la chiamata a Gemini: {str(e)}")
    
    def _chat_openai(self, model: str, messages: list, options: Dict[str, Any]) -> Dict[str, Any]:
        """Chat con OpenAI."""
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=options.get('temperature', 0.1),
            max_tokens=options.get('num_predict', 512),
            top_p=options.get('top_p', 0.95)
        )
        
        return {
            "message": {
                "role": "assistant",
                "content": response.choices[0].message.content
            }
        }


def get_llm_provider(provider: str = None) -> LLMProvider:
    """Factory function per ottenere un provider LLM."""
    return LLMProvider(provider)


def llm_chat(model: str, messages: list, options: Dict[str, Any] = None, 
             provider: str = None) -> Dict[str, Any]:
    """Funzione helper per inviare una richiesta al provider LLM configurato."""
    llm = get_llm_provider(provider)
    return llm.chat(model, messages, options)