"""
handlers/llm_handler.py
------------------------
LLM inference integration for NeuralNexus AI tutoring.

Loads the Phi-3 GGUF model once at module import time and exposes a
per-session ``ModelPipeline`` via the ``create_chat_session()`` factory.

Model location:  ./Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf
"""

import os
import logging

try:
    from llama_cpp import Llama
    _LLAMA_AVAILABLE = True
except ImportError:
    _LLAMA_AVAILABLE = False
    logging.warning(
        "llm_handler: llama_cpp not installed — LLM features will be disabled."
    )

MODEL_PATH = "./Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf"

# System persona injected at the start of every conversation
_SYSTEM_MESSAGES = [
    {
        "role": "user",
        "content": (
            "You are a virtual assistant capable of only answering questions "
            "related to Science and Technology. "
            "If the question is unrelated, reply in denial."
        ),
    },
    {
        "role": "user",
        "content": "What is an Operating System?",
    },
    {
        "role": "assistant",
        "content": (
            "An operating system is software that enables applications to "
            "interact with a computer's hardware."
        ),
    },
]


# ---------------------------------------------------------------------------
# Message formatting helpers
# ---------------------------------------------------------------------------

def _format_chat_template(messages: list) -> str:
    """Render a list of role/content dicts into the Phi-3 prompt template."""
    output = ""
    for msg in messages:
        if msg["role"] == "user":
            output += "<|user|>\n" + msg["content"] + "\n<|end|>\n<|assistant|>\n"
        elif msg["role"] == "assistant":
            output += msg["content"] + "\n<|end|>\n"
    return output


def _make_message(role: str, content: str) -> dict:
    return {"role": role, "content": content}


# ---------------------------------------------------------------------------
# Per-session pipeline
# ---------------------------------------------------------------------------

class ModelPipeline:
    """
    Stateful chat pipeline that maintains a rolling context window for a
    single user session.

    Args:
        model:          An initialised ``llama_cpp.Llama`` instance.
        context_limit:  Number of previous exchange pairs to include in each
                        prompt (default: 1).
    """

    def __init__(self, model, context_limit: int = 1) -> None:
        self._model = model
        self._context_limit = context_limit
        self._context: list = []

    def add_message(self, user_input: str) -> str:
        """
        Process a user message through the LLM and return the assistant reply.

        Updates the internal context with the new exchange.
        """
        user_msg = _make_message("user", user_input)
        context_window = (
            _SYSTEM_MESSAGES
            + self._context[-(self._context_limit * 2):]
        )
        context_window.append(user_msg)

        prompt = _format_chat_template(context_window)
        output = self._model(prompt, max_tokens=80, top_p=0.5, temperature=0.6)
        reply_text = output["choices"][0].get("text", "").strip()
        # Collapse multi-line model output into a single line
        reply_text = "".join(reply_text.split("\n"))

        self._context.append(user_msg)
        self._context.append(_make_message("assistant", reply_text))
        return reply_text


# ---------------------------------------------------------------------------
# Module-level model singleton — loaded lazily on first use
# ---------------------------------------------------------------------------

_model = None


def _get_model():
    """Load the Llama model once and return the singleton. Returns None if unavailable."""
    global _model
    if _model is not None:
        return _model
    if not _LLAMA_AVAILABLE:
        return None
    if not os.path.exists(MODEL_PATH):
        logging.warning(
            f"llm_handler: model file not found at '{MODEL_PATH}' — LLM features disabled."
        )
        return None
    logging.info("llm_handler: loading Llama model (first use)…")
    _model = Llama(model_path=MODEL_PATH, verbose=False, use_mlock=True, device="cuda")
    logging.info("llm_handler: model loaded.")
    return _model


def create_chat_session() -> "ModelPipeline | None":
    """Factory: return a fresh ``ModelPipeline`` backed by the shared model.

    Returns ``None`` when the model is unavailable (no llama_cpp / no model file).
    """
    m = _get_model()
    if m is None:
        return None
    return ModelPipeline(m)


# Legacy alias used by LlmService
Chat = create_chat_session
