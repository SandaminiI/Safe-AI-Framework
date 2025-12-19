import os, time
from typing import AsyncIterator, List
import google.generativeai as genai
from google.api_core.exceptions import NotFound, PermissionDenied, InvalidArgument, ResourceExhausted

API_KEY = os.getenv("GEMINI_API_KEY", "")
USER_MODEL = (os.getenv("GEMINI_MODEL") or "").strip()

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Put it in .env or export it.")

genai.configure(api_key=API_KEY)

def _list_models() -> List[str]:
    out = []
    try:
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                out.append(m.name.replace("models/", ""))
    except Exception:
        pass
    return out

CANDIDATES: List[str] = []
if USER_MODEL:
    CANDIDATES.append(USER_MODEL)
CANDIDATES += [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite-001",
    "gemini-flash-latest",
    "gemini-2.5-pro",
]
_seen = set(CANDIDATES)
for nm in _list_models():
    if nm not in _seen:
        CANDIDATES.append(nm)
        _seen.add(nm)

SYSTEM_NUDGE = (
    "Return EXACTLY ONE fenced code block with the appropriate language identifier. "
    "If multiple files are needed, concatenate them inside a single ```txt fence using:\n"
    "=== FILE: <relative/path.ext> ===\n"
    "<contents>\n\n"
    "No prose before/after the fence. CRITICAL: Generate COMPLETE code - never truncate or use placeholders."
)

GEN_CFG = {
    "temperature": 0.3,
    "max_output_tokens": 16384,
    "top_p": 0.95,
    "top_k": 40,
}

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

def _init_model(name: str):
    m = genai.GenerativeModel(name)
    try:
        m.count_tokens("ping")
    except Exception:
        pass
    return m

def _pick_model() -> str:
    for nm in CANDIDATES:
        try:
            _init_model(nm)
            return nm
        except (NotFound, PermissionDenied, InvalidArgument):
            continue
        except Exception:
            continue
    return "gemini-2.5-flash"

_MODEL_NAME = _pick_model()
_MODEL = _init_model(_MODEL_NAME)

def _fallback_after(curr: str) -> str:
    try:
        i = CANDIDATES.index(curr)
    except ValueError:
        return CANDIDATES[0]
    return CANDIDATES[(i + 1) % len(CANDIDATES)]

def _join_parts_from_response(resp) -> str:
    buf: List[str] = []
    if not hasattr(resp, "candidates") or not resp.candidates:
        return ""
    for cand in resp.candidates:
        parts = getattr(getattr(cand, "content", None), "parts", []) or []
        for p in parts:
            t = getattr(p, "text", "") or ""
            if t:
                buf.append(t)
    return "".join(buf).strip()

def _ensure_single_fence(text: str, prefer_lang: str = "txt") -> str:
    t = (text or "").strip()
    if "```" in t:
        return t
    return f"```{prefer_lang}\n{t}\n```"

def _diagnostic(resp) -> str:
    reason = None
    try:
        if resp and resp.candidates:
            reason = getattr(resp.candidates[0], "finish_reason", None)
    except Exception:
        pass
    
    reason_name = str(reason) if reason else "UNKNOWN"
    msg = f"// Generation incomplete. Finish reason: {reason_name}\n"
    if "RECITATION" in reason_name:
        msg += "// Model detected potential copyright content. Try rephrasing your prompt.\n"
    elif "MAX_TOKENS" in reason_name or "LENGTH" in reason_name:
        msg += "// Output exceeded token limit. Try breaking into smaller components.\n"
    elif "SAFETY" in reason_name:
        msg += "// Safety filter triggered. Adjust prompt to be more neutral.\n"
    return _ensure_single_fence(msg)

async def stream_code(prompt: str) -> AsyncIterator[str]:
    """Generate code with retry logic and streaming fallback. Always one fenced block."""
    global _MODEL, _MODEL_NAME

    contents = [{"role": "user", "parts": [{"text": f"{SYSTEM_NUDGE}\n\n{prompt}"}]}]

    for attempt in range(3):
        try:
            print(f" Generating with '{_MODEL_NAME}' (attempt {attempt+1}/3)...")
            resp = _MODEL.generate_content(
                contents=contents,
                generation_config=GEN_CFG,
                safety_settings=SAFETY,
                stream=False
            )
            text = _join_parts_from_response(resp)
            finish_reason = None
            try:
                if resp and resp.candidates:
                    finish_reason = getattr(resp.candidates[0], "finish_reason", None)
            except Exception:
                pass

            if text and finish_reason and "STOP" in str(finish_reason):
                print(f"   ✓ Complete generation received ({len(text)} chars)")
                yield _ensure_single_fence(text, prefer_lang="txt")
                return

            if text and len(text) > 500:
                print(f"   ⚠ Partial generation ({len(text)} chars), reason: {finish_reason}")
                if text.rstrip().endswith("```"):
                    yield text
                    return

            if not text or len(text) < 500:
                print(f"   ⚠ Retrying with streaming (non-streaming gave {len(text)} chars)...")
                st = _MODEL.generate_content(
                    contents=contents,
                    generation_config=GEN_CFG,
                    safety_settings=SAFETY,
                    stream=True
                )
                acc: List[str] = []
                last_finish_reason = None
                try:
                    for ch in st:
                        try:
                            if hasattr(ch, 'candidates') and ch.candidates:
                                last_finish_reason = getattr(ch.candidates[0], 'finish_reason', None)
                        except Exception:
                            pass
                        if getattr(ch, "candidates", None):
                            for c in ch.candidates:
                                parts = getattr(getattr(c, "content", None), "parts", []) or []
                                for p in parts:
                                    t = getattr(p, "text", "") or ""
                                    if t:
                                        acc.append(t)
                        else:
                            t = getattr(ch, "text", "") or ""
                            if t:
                                acc.append(t)
                except StopIteration:
                    pass
                except Exception as e:
                    print(f"   ⚠ Streaming error: {e}")

                text = "".join(acc).strip()
                print(f"   ℹ Streaming complete: {len(text)} chars, reason: {last_finish_reason}")
                if text and (not last_finish_reason or "STOP" in str(last_finish_reason)):
                    yield _ensure_single_fence(text, prefer_lang="txt")
                    return

            if attempt == 2 and text:
                warning = f"// Warning: Generation may be incomplete (finish reason: {finish_reason})\n\n"
                yield _ensure_single_fence(warning + text, prefer_lang="txt")
                return

            if not text:
                yield _diagnostic(resp)
                return

        except ResourceExhausted:
            nxt = _fallback_after(_MODEL_NAME)
            print(f"   ⚠ Quota hit on '{_MODEL_NAME}', switching to {nxt}")
            _MODEL_NAME, _MODEL = nxt, _init_model(nxt)
            time.sleep(1.0)
            continue
        except (NotFound, PermissionDenied, InvalidArgument):
            nxt = _fallback_after(_MODEL_NAME)
            print(f"   ✗ Access error on '{_MODEL_NAME}', switching to {nxt}")
            _MODEL_NAME, _MODEL = nxt, _init_model(nxt)
            time.sleep(0.5)
            continue
        except Exception as e:
            print(f"   ✗ Unexpected: {type(e).__name__}: {e}")
            if attempt < 2:
                nxt = _fallback_after(_MODEL_NAME)
                _MODEL_NAME, _MODEL = nxt, _init_model(nxt)
                time.sleep(0.5)
                continue
            yield _ensure_single_fence(f"// Unexpected error: {type(e).__name__}\n// {str(e)}")
            return

    yield _ensure_single_fence("// Maximum retry attempts exceeded.")
