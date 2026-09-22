# Python SDK

```python
from jev_agent_bridge import AgentBridgeClient

client = AgentBridgeClient("http://localhost:8000")

result = client.decide(
    state="Deployment failed",
    question="What should happen next?",
    options=[
        {"id": "retry", "description": "Retry deployment"},
        {"id": "abort", "description": "Abort deployment"},
    ],
)

print(result["decision"]["id"])
print(result["selected_probability"])
```