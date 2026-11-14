import json

REQUEST = {
    "system": "Answer in Vietnamese, at most two sentences.",
    "user": "Phí giao trong cùng quận là bao nhiêu?",
    "max_tokens": 400,
    "temperature": 0.2,
}


def openai_style(req, model):
    return {"model": model, "instructions": req["system"], "input": req["user"],
            "max_output_tokens": req["max_tokens"], "temperature": req["temperature"]}


def bedrock_converse(req, model_id):
    return {"modelId": model_id, "system": [{"text": req["system"]}],
            "messages": [{"role": "user", "content": [{"text": req["user"]}]}],
            "inferenceConfig": {"maxTokens": req["max_tokens"], "temperature": req["temperature"]}}


def vertex_generate(req):
    return {"systemInstruction": {"parts": [{"text": req["system"]}]},
            "contents": [{"role": "user", "parts": [{"text": req["user"]}]}],
            "generationConfig": {"maxOutputTokens": req["max_tokens"], "temperature": req["temperature"]}}


SAMPLE_REPLIES = {
    "openai": {"output_text": "Phí là 15.000 đồng.", "usage": {"input_tokens": 41, "output_tokens": 9}},
    "bedrock": {"output": {"message": {"role": "assistant", "content": [{"text": "Phí là 15.000 đồng."}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 41, "outputTokens": 9, "totalTokens": 50}},
    "vertex": {"candidates": [{"content": {"parts": [{"text": "Phí là 15.000 đồng."}]}, "finishReason": "STOP"}],
               "usageMetadata": {"promptTokenCount": 41, "candidatesTokenCount": 9}},
}


def normalize(kind, reply):
    if kind == "openai":
        return reply["output_text"], reply["usage"]["input_tokens"], reply["usage"]["output_tokens"]
    if kind == "bedrock":
        return reply["output"]["message"]["content"][0]["text"], reply["usage"]["inputTokens"], reply["usage"]["outputTokens"]
    return reply["candidates"][0]["content"]["parts"][0]["text"], reply["usageMetadata"]["promptTokenCount"], reply["usageMetadata"]["candidatesTokenCount"]


payloads = {
    "openai-style (Azure v1 uses the same body, model = deployment name)": openai_style(REQUEST, "my-deployment"),
    "bedrock converse": bedrock_converse(REQUEST, "<model id or inference profile>"),
    "vertex generateContent": vertex_generate(REQUEST),
}
for name, body in payloads.items():
    print(name)
    print("  top-level keys:", sorted(body))
    print("  token cap field:", json.dumps({k: v for k, v in body.items() if k in ("max_output_tokens", "inferenceConfig", "generationConfig")}))

print("\nafter normalize (text, input tokens, output tokens):")
for kind, reply in SAMPLE_REPLIES.items():
    print(f"  {kind:8s}", normalize(kind, reply))
