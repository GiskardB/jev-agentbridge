/** Minimal TypeScript SDK for JEV-CPU-AgentBridge. */

export interface Option {
  id: string
  description: string
}

export interface DecisionRequest {
  state: string | Record<string, unknown> | unknown[]
  question: string
  options: Option[]
}

export interface DecisionResult {
  decision: Option
  probabilities: Record<string, number>
  selected_probability: number
  accepted: boolean
  metadata: Record<string, unknown>
}

export class AgentBridgeClient {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  async decide(request: DecisionRequest): Promise<DecisionResult> {
    const response = await fetch(`${this.baseUrl}/v1/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`JEV-CPU-AgentBridge request failed: ${response.status}`)
    }

    return (await response.json()) as DecisionResult
  }

  async decideBatch(
    state: string | Record<string, unknown> | unknown[],
    decisions: Array<Omit<DecisionRequest, 'state'>>,
  ): Promise<DecisionResult[]> {
    const response = await fetch(`${this.baseUrl}/v1/decide/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, decisions }),
    })

    if (!response.ok) {
      throw new Error(`JEV-CPU-AgentBridge request failed: ${response.status}`)
    }

    const body = (await response.json()) as { decisions: DecisionResult[] }
    return body.decisions
  }

  async health(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/health`)
    if (!response.ok) throw new Error(`Health check failed: ${response.status}`)
    return (await response.json()) as { status: string }
  }

  async ready(): Promise<{ status: string; model: string }> {
    const response = await fetch(`${this.baseUrl}/ready`)
    if (!response.ok) throw new Error(`Readiness check failed: ${response.status}`)
    return (await response.json()) as { status: string; model: string }
  }

  async info(): Promise<Record<string, unknown>> {
    const response = await fetch(`${this.baseUrl}/v1/info`)
    if (!response.ok) throw new Error(`Info request failed: ${response.status}`)
    return (await response.json()) as Record<string, unknown>
  }
}