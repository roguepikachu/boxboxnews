"""Track Gemini API token usage and estimate cost per pipeline run."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (USD) — update if pricing changes
# Source: Google AI Studio pricing page
MODEL_PRICING = {
    # Gemini 2.5 Flash (text in/out)
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "thinking": 0.30},
    # Gemini 3 Flash
    "gemini-3-flash": {"input": 0.15, "output": 0.60, "thinking": 0.30},
    # Gemini 2.5 Pro
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "thinking": 2.50},
    # Gemini 3 Pro Image (Nano Banana Pro) — per-image pricing
    "gemini-3-pro-image-preview": {"input": 0.15, "output": 0.60, "image_output": 0.0315},
    "nano-banana-pro-preview": {"input": 0.15, "output": 0.60, "image_output": 0.0315},
    # Gemini 2.5 Flash Image (Nano Banana)
    "gemini-2.5-flash-image": {"input": 0.15, "output": 0.60, "image_output": 0.0315},
    # Imagen 4
    "imagen-4.0-generate-001": {"per_image": 0.04},
    "imagen-4.0-fast-generate-001": {"per_image": 0.02},
    "imagen-4.0-ultra-generate-001": {"per_image": 0.08},
}

# Fallback for unknown models
DEFAULT_PRICING = {"input": 0.15, "output": 0.60}


@dataclass
class CostTracker:
    """Accumulates API usage across a pipeline run."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_thinking_tokens: int = 0
    total_image_gen_calls: int = 0
    total_cost_usd: float = 0.0
    calls: list = field(default_factory=list)

    def record_generate_content(self, model: str, response) -> None:
        """Record token usage from a generate_content response."""
        um = getattr(response, "usage_metadata", None)
        if not um:
            return

        input_tokens = getattr(um, "prompt_token_count", 0) or 0
        output_tokens = getattr(um, "candidates_token_count", 0) or 0
        thinking_tokens = getattr(um, "thoughts_token_count", 0) or 0

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_thinking_tokens += thinking_tokens

        # Calculate cost
        model_key = model.split("/")[-1]  # strip "models/" prefix if present
        pricing = MODEL_PRICING.get(model_key, DEFAULT_PRICING)

        input_cost = input_tokens / 1_000_000 * pricing.get("input", 0.15)
        output_cost = output_tokens / 1_000_000 * pricing.get("output", 0.60)
        thinking_cost = thinking_tokens / 1_000_000 * pricing.get("thinking", pricing.get("input", 0.15))

        # Check if response contains a generated image
        image_cost = 0.0
        has_image = False
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        has_image = True
                        break
        except (AttributeError, IndexError):
            pass

        if has_image:
            image_cost = pricing.get("image_output", 0.0315)

        call_cost = input_cost + output_cost + thinking_cost + image_cost
        self.total_cost_usd += call_cost

        self.calls.append({
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "has_image": has_image,
            "cost_usd": call_cost,
        })

    def record_image_generation(self, model: str) -> None:
        """Record an Imagen API call."""
        self.total_image_gen_calls += 1
        model_key = model.split("/")[-1]
        pricing = MODEL_PRICING.get(model_key, {})
        cost = pricing.get("per_image", 0.04)
        self.total_cost_usd += cost

        self.calls.append({
            "model": model_key,
            "type": "image_generation",
            "cost_usd": cost,
        })

    # USD to INR conversion rate — update periodically
    USD_TO_INR = 85.0

    def summary(self) -> str:
        """Return a formatted cost summary."""
        cost_inr = self.total_cost_usd * self.USD_TO_INR
        lines = [
            "=== Cost Summary ===",
            f"Gemini API calls: {len([c for c in self.calls if 'input_tokens' in c])}",
            f"  Input tokens:    {self.total_input_tokens:,}",
            f"  Output tokens:   {self.total_output_tokens:,}",
            f"  Thinking tokens: {self.total_thinking_tokens:,}",
        ]
        if self.total_image_gen_calls:
            lines.append(f"Imagen calls:      {self.total_image_gen_calls}")
        lines.append(f"Estimated cost:    ${self.total_cost_usd:.4f} (~₹{cost_inr:.2f})")
        return "\n".join(lines)


# Global singleton used across the pipeline
tracker = CostTracker()
