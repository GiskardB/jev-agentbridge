# TypeScript SDK

```ts
import { AgentBridgeClient } from '@jev-cpu/agentbridge'

const client = new AgentBridgeClient('http://localhost:8000')

const result = await client.decide({
  state: 'Deployment failed',
  question: 'What should happen next?',
  options: [
    { id: 'retry', description: 'Retry deployment' },
    { id: 'abort', description: 'Abort deployment' },
  ],
})

console.log(result.decision.id)
console.log(result.selected_probability)
```