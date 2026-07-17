import os
import time
import re
from typing import List, Dict, Any, Callable, Optional
import google.generativeai as genai
import cohere
from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:
    Groq = None

# Define path to look for .env file
dotenv_paths = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", ".env"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
]

# Load from first available env path
env_loaded = False
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)
        env_loaded = True
        break
if not env_loaded:
    load_dotenv()

def get_api_key() -> str:
    """Retrieves the Gemini API Key from environment variables."""
    return os.environ.get("GEMINI_API_KEY", "")

def get_cohere_api_key() -> str:
    """Retrieves the Cohere API Key from environment variables."""
    return os.environ.get("COHERE_API_KEY", "")

def get_groq_api_key() -> str:
    """Retrieves the Groq API Key from environment variables."""
    return os.environ.get("GROQ_API_KEY", "")

def get_groq_model_name() -> str:
    """Retrieves the default Groq model name from environment variables."""
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

def get_model_name() -> str:
    """Retrieves the default model name from environment variables."""
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

def configure_gemini() -> bool:
    """Configure Gemini API. Returns True if successful."""
    api_key = get_api_key()
    if not api_key or api_key == "your_gemini_api_key_here":
        return False
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False

def configure_cohere() -> bool:
    """Configure Cohere API. Returns True if successful."""
    api_key = get_cohere_api_key()
    if not api_key or api_key == "your_cohere_api_key_here":
        return False
    return True

def configure_groq() -> bool:
    """Configure Groq API. Returns True if a usable key + package are present."""
    if Groq is None:
        return False
    api_key = get_groq_api_key()
    if not api_key or api_key == "your_groq_api_key_here":
        return False
    return True

def call_cohere(prompt: str) -> str:
    """
    Call Cohere API as fallback when Gemini quota is exceeded.
    Uses command-r model for text generation.
    """
    api_key = get_cohere_api_key()
    if not api_key:
        raise Exception("Cohere API key not configured.")
    
    co = cohere.ClientV2(api_key=api_key)
    response = co.chat(
        model="command-r-plus-08-2024",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.message.content[0].text.strip()

def call_groq(prompt: str) -> str:
    """
    Call the Groq API (fast Llama/Gemma inference). Can be used as the primary
    provider or as a fallback when Gemini/Cohere are unavailable or rate-limited.
    """
    if Groq is None:
        raise Exception("Groq package not installed. Run: pip install groq")

    api_key = get_groq_api_key()
    if not api_key:
        raise Exception("Groq API key not configured.")

    client = Groq(api_key=api_key)
    model_name = get_groq_model_name()
    chat_completion = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )
    return chat_completion.choices[0].message.content.strip()

def call_gemini_with_retry(
    model: genai.GenerativeModel,
    prompt: str,
    max_retries: int = 5,
    initial_delay: float = 12.0,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    current_step: int = 0,
    total_steps: int = 1,
    progress_status_prefix: str = ""
) -> str:
    """
    Calls the Gemini API generate_content method, wrapping it with an auto-retry loop
    and backoff mechanism when encountering ResourceExhausted (429) rate limit errors.
    """
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                # Add a brief, safe 2-second sleep between queries to help pace requests
                # under the 5 RPM limit
                time.sleep(2)
                return response.text.strip()
            raise Exception("Received empty response from Gemini API.")
            
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = (
                "429" in err_msg or 
                "quota" in err_msg.lower() or 
                "resourceexhausted" in err_msg.lower() or 
                "limit" in err_msg.lower()
            )
            
            if is_rate_limit and attempt < max_retries - 1:
                # Determine how long we should sleep
                sleep_time = delay
                # Extract specific retry duration if provided in error message
                # Example: "Please retry in 48.949520988s."
                seconds_match = re.search(r'retry in ([\d\.]+)s', err_msg)
                if seconds_match:
                    try:
                        sleep_time = float(seconds_match.group(1)) + 2.0
                    except Exception:
                        pass
                
                # Cap the minimum sleep time to 15 seconds to ensure we clear the RPM window
                sleep_time = max(sleep_time, 15.0)
                
                # Report cooling down to the UI
                if progress_callback:
                    # Keep counting down live so user knows the app is active
                    for remaining in range(int(sleep_time), 0, -5):
                        progress_callback(
                            current_step,
                            total_steps,
                            f"{progress_status_prefix} ⚠️ Rate limit hit! Cooling down for {remaining}s..."
                        )
                        time.sleep(min(remaining, 5))
                else:
                    time.sleep(sleep_time)
                
                # Double the backoff delay for the next attempt
                delay *= 2
            else:
                # Max retries reached or non-rate-limit error
                # Try Groq first (fast + generous free tier), then Cohere as fallback
                if configure_groq():
                    try:
                        if progress_callback:
                            progress_callback(
                                current_step, total_steps,
                                f"{progress_status_prefix} 🔄 Switching to Groq fallback..."
                            )
                        return call_groq(prompt)
                    except Exception:
                        pass
                if configure_cohere():
                    try:
                        if progress_callback:
                            progress_callback(
                                current_step, total_steps,
                                f"{progress_status_prefix} 🔄 Switching to Cohere fallback..."
                            )
                        return call_cohere(prompt)
                    except Exception as cohere_err:
                        raise Exception(f"Gemini failed: {str(e)}. Groq/Cohere fallback also failed: {str(cohere_err)}")
                raise e
                
    # If all retries exhausted, try Groq then Cohere
    if configure_groq():
        try:
            return call_groq(prompt)
        except Exception:
            pass
    if configure_cohere():
        try:
            return call_cohere(prompt)
        except Exception:
            pass
    raise Exception("Max retries reached without a successful API response.")

def verify_api_connection(provider: str = "auto") -> Dict[str, Any]:
    """
    Verifies connection to the selected AI provider.

    Args:
        provider: "auto" (tries Gemini -> Groq -> Cohere in order),
                  "gemini", "groq", or "cohere" to test one specific provider.
    """
    gemini_ok = configure_gemini()
    groq_ok = configure_groq()
    cohere_ok = configure_cohere()

    def try_gemini():
        model_name = get_model_name()
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Ping. Reply with 'Pong' only.")
        if response and response.text:
            return {
                "success": True,
                "response": response.text.strip(),
                "model_used": f"gemini/{model_name}"
            }
        raise Exception("Received empty response from Gemini API.")

    def try_groq():
        response = call_groq("Ping. Reply with 'Pong' only.")
        return {
            "success": True,
            "response": response,
            "model_used": f"groq/{get_groq_model_name()}"
        }

    def try_cohere():
        response = call_cohere("Ping. Reply with 'Pong' only.")
        return {
            "success": True,
            "response": response,
            "model_used": "cohere/command-r-plus"
        }

    candidates = {
        "gemini": (gemini_ok, try_gemini),
        "groq": (groq_ok, try_groq),
        "cohere": (cohere_ok, try_cohere),
    }

    if provider in candidates:
        order = [provider]
    else:
        order = ["gemini", "groq", "cohere"]  # auto

    errors = []
    for name in order:
        is_configured, fn = candidates[name]
        if not is_configured:
            errors.append(f"{name}: not configured")
            continue
        try:
            result = fn()
            if provider == "auto" and name != "gemini":
                result["warning"] = f"Using {name} (earlier provider(s) unavailable)."
            return result
        except Exception as e:
            errors.append(f"{name}: {str(e)}")

    return {
        "success": False,
        "error": "; ".join(errors) if errors else "No provider configured. Add an API key in config/.env or the sidebar."
    }

# Prompt definitions for different output formats
FORMAT_PROMPTS = {
    "Executive Summary": (
        "A highly polished, narrative business summary highlighting core findings, "
        "strategic implications, and key recommendations. Organize with clear headings, "
        "bold text for key metrics, and bulleted takeaways where appropriate."
    ),
    "Action-Items Checklist": (
        "A structured checklist of tasks, milestones, and actionable recommendations. "
        "Use markdown checkbox syntax (e.g., - [ ] Task name) and assign tasks to logical owners "
        "or departments if mentioned. Group items by priority (High, Medium, Low) or project phases."
    ),
    "Q&A Study Guide": (
        "A comprehensive Q&A Study Guide containing key questions and detailed answers derived "
        "directly from the source text. Focus on complex concepts, definitions, core hypotheses, "
        "and data points. Use a Q: and A: format."
    ),
    "Core Timeline": (
        "A detailed chronological timeline listing key events, project phases, historical dates, "
        "and milestones. Format each entry as '**[Date/Time]** - Event details' and ensure chronological order."
    )
}

def generate_map_reduce_summary(
    chunks: List[Dict[str, Any]],
    format_type: str = "Executive Summary",
    provider: str = "auto",
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executes the manual Map-Reduce loop on document chunks.
    
    Args:
        chunks: List of dictionaries representing document chunks.
        format_type: Type of final report (e.g., Executive Summary, Action-Items Checklist).
        provider: "auto" (Gemini -> Groq -> Cohere fallback chain), "gemini", "groq", or "cohere"
                  to force one specific provider (no automatic fallback in that case).
        progress_callback: Callable function taking (current_step, total_steps, status_text)
                           to report progress to frontend.
                           
    Returns:
        Dictionary containing:
            - "success": (bool)
            - "final_summary": (str)
            - "intermediate_summaries": List[str]
            - "error": (str)
    """
    result = {
        "success": False,
        "final_summary": "",
        "intermediate_summaries": [],
        "error": None
    }
    
    if not chunks:
        result["error"] = "No text chunks provided for summarization."
        return result

    gemini_ok = configure_gemini()
    groq_ok = configure_groq()
    cohere_ok = configure_cohere()

    if provider == "gemini" and not gemini_ok:
        result["error"] = "Gemini selected but GEMINI_API_KEY is not configured."
        return result
    if provider == "groq" and not groq_ok:
        result["error"] = "Groq selected but GROQ_API_KEY is not configured."
        return result
    if provider == "cohere" and not cohere_ok:
        result["error"] = "Cohere selected but COHERE_API_KEY is not configured."
        return result
    if provider == "auto" and not (gemini_ok or groq_ok or cohere_ok):
        result["error"] = "No API key configured. Please add GEMINI_API_KEY, GROQ_API_KEY, or COHERE_API_KEY."
        return result

    # Set up Gemini model if it's relevant to this run (auto chain or explicit gemini)
    model = None
    if gemini_ok and provider in ("auto", "gemini"):
        try:
            model_name = get_model_name() or "gemini-2.5-flash"
            model = genai.GenerativeModel(model_name)
        except Exception:
            model = None

    def call_selected(prompt: str, idx: int, total_steps: int, prefix_status: str) -> str:
        """Dispatches the prompt to the chosen provider. 'auto' keeps the Gemini->Groq->Cohere chain."""
        if provider == "groq":
            return call_groq(prompt)
        if provider == "cohere":
            return call_cohere(prompt)
        if provider == "gemini":
            if not model:
                raise Exception("Gemini model unavailable.")
            return call_gemini_with_retry(
                model=model, prompt=prompt, progress_callback=progress_callback,
                current_step=idx, total_steps=total_steps, progress_status_prefix=prefix_status
            )
        # provider == "auto"
        if model:
            return call_gemini_with_retry(
                model=model, prompt=prompt, progress_callback=progress_callback,
                current_step=idx, total_steps=total_steps, progress_status_prefix=prefix_status
            )
        if groq_ok:
            return call_groq(prompt)
        if cohere_ok:
            return call_cohere(prompt)
        raise Exception("No AI provider available.")

    total_chunks = len(chunks)
    intermediate_summaries = []
    total_steps = total_chunks + 1  # Map steps + 1 Reduce step
    
    # ------------------ MAP PHASE ------------------
    if progress_callback:
        progress_callback(0, total_steps, "Starting Map Phase: Summarizing chunks independently...")
        
    for idx, chunk in enumerate(chunks):
        chunk_idx = idx + 1
        prefix_status = f"Map Phase: Processing chunk {chunk_idx}/{total_chunks} (Pages: {chunk['pages']})"
        
        if progress_callback:
            progress_callback(idx, total_steps, f"{prefix_status}...")
            
        map_prompt = f"""You are an expert technical analyst. Summarize the following document chunk.
Retain all key facts, specific metrics, project names, timelines, and main arguments.
Do not introduce external facts or speculate.

---
{chunk['text']}
---

Intermediate Summary:"""
        
        try:
            summary = call_selected(map_prompt, idx, total_steps, prefix_status)
            intermediate_summaries.append(summary)
        except Exception as e:
            result["error"] = f"Error during Map phase at chunk {chunk_idx}: {str(e)}"
            return result
            
    result["intermediate_summaries"] = intermediate_summaries
    
    # ------------------ REDUCE PHASE ------------------
    prefix_status = "Reduce Phase: Synthesizing final report"
    if progress_callback:
        progress_callback(total_chunks, total_steps, f"{prefix_status}...")
        
    combined_intermediates = "\n\n---\n\n".join(intermediate_summaries)
    target_format_description = FORMAT_PROMPTS.get(format_type, FORMAT_PROMPTS["Executive Summary"])
    
    reduce_prompt = f"""You are an expert chief editor. Combine the following intermediate summaries of a document into a final, unified report.
You must adhere strictly to the target format: {target_format_description}

Maintain professional tone, logical flow, and ensure all key facts, metrics, and takeaways from the intermediate summaries are preserved.
Do not make up facts, names, or timelines.

---
Intermediate Summaries:
{combined_intermediates}
---

Final Formatted Report:"""

    try:
        final_summary = call_selected(reduce_prompt, total_chunks, total_steps, prefix_status)
        result["final_summary"] = final_summary
        result["success"] = True
    except Exception as e:
        result["error"] = f"Error during Reduce phase: {str(e)}"
        result["success"] = False
        
    if progress_callback and result["success"]:
        progress_callback(total_steps, total_steps, "Summarization Completed Successfully!")
        
    return result

if __name__ == "__main__":
    print("Testing Gemini API Connection...")
    conn_result = verify_api_connection()
    if conn_result["success"]:
        print(f"Connection Successful! Model: {conn_result['model_used']}")
        print(f"Response: {conn_result['response']}")
    else:
        print(f"Connection Failed: {conn_result['error']}")