/** Minimal TypeScript SDK for JEV-AgentBridge. */

export interface Option {
  id: string
  description: string
}

export type State = string | Record<string, unknown> | unknown[]

/** choice: one option. noul: yes/no (no options). score: options are levels, lowest first. */
export type QuestionType = 'choice' | 'noul' | 'score'

export interface DecisionRequest {
  state: State
  question: string
  /** Default 'choice'. */
  type?: QuestionType
  /** Required for choice and score; omitted for noul. */
  options?: Option[]
  /** noul only: what "yes" / "no" mean, when not obvious. */
  yes_description?: string
  no_description?: string
  /** score only: levels on each side of the chosen one counted towards `accepted` (default 1). */
  score_tolerance?: number
  /** Acceptance threshold for this call; defaults to the service's configured value. */
  min_selected_probability?: number
}

export interface DecisionResult {
  type: QuestionType
  /** Most likely option; for noul `yes` or `no`, for score the level. */
  decision: Option
  /** One probability per option id. */
  probabilities: Record<string, number>
  selected_probability: number
  accepted: boolean
  threshold: number
  /** score only: expected level, 0 (first level) to options.length - 1. */
  score: number | null
  /** noul only: probability of yes. */
  noul: number | null
  /** score only: probability of the chosen level ± score_tolerance; what `accepted` uses. */
  score_window_probability: number | null
  score_tolerance: number | null
  metadata: {
    engine: string
    model: string
    model_revision: string
    mode: 'direct' | 'shared'
    latency_ms: number
    /** false when the engine lacks this type and the bridge emulated it as a choice. */
    native_type: boolean
    input_tokens?: number
    engine_details?: Record<string, unknown>
  }
}

export interface BridgeErrorBody {
  error: { code: string; message: string; request_id: string }
}

export class BridgeError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'BridgeError'
  }
}

export interface GateOutcome {
  decisionId: string
  /** "jev" when the Bridge answered with accepted=true, "fallback" otherwise. */
  source: 'jev' | 'fallback'
  jevResult: DecisionResult | null
  /** Set when the Bridge could not be used at all (down, timeout, error response). */
  error?: string
}

/** Must return one of the option ids, typically by asking your LLM. */
export type Fallback = (request: DecisionRequest) => Promise<string> | string

export class AgentBridgeClient {
  private readonly baseUrl: string

  constructor(
    baseUrl = 'http://localhost:8000',
    private readonly timeoutMs = 30_000,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      signal: AbortSignal.timeout(this.timeoutMs),
    })
    const body = (await response.json().catch(() => null)) as unknown
    if (!response.ok) {
      const error = (body as BridgeErrorBody | null)?.error
      throw new BridgeError(
        response.status,
        error?.code ?? 'HTTP_ERROR',
        error?.message ?? `JEV-AgentBridge request failed: ${response.status}`,
      )
    }
    return body as T
  }

  private post<T>(path: string, payload: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  }

  decide(request: DecisionRequest): Promise<DecisionResult> {
    return this.post<DecisionResult>('/v1/decide', request)
  }

  /** noul decision: `decision.id` is 'yes' or 'no', `noul` is P(yes). */
  yesNo(request: Omit<DecisionRequest, 'type' | 'options'>): Promise<DecisionResult> {
    return this.decide({ ...request, type: 'noul' })
  }

  /** score decision over `levels`, lowest first: `score` is the expected level. */
  score(
    request: Omit<DecisionRequest, 'type' | 'options' | 'yes_description' | 'no_description'>,
    levels: Option[],
  ): Promise<DecisionResult> {
    return this.decide({ ...request, type: 'score', options: levels })
  }

  /**
   * Gate pattern: use JEV's answer when it is confident, otherwise call `fallback`
   * (your LLM). The fallback also covers the Bridge being down, so the gate never
   * breaks the agent.
   */
  async decideOrFallback(request: DecisionRequest, fallback: Fallback): Promise<GateOutcome> {
    let result: DecisionResult
    try {
      result = await this.decide(request)
    } catch (error) {
      return {
        decisionId: await fallback(request),
        source: 'fallback',
        jevResult: null,
        error: error instanceof Error ? error.message : String(error),
      }
    }
    if (result.accepted) {
      return { decisionId: result.decision.id, source: 'jev', jevResult: result }
    }
    return { decisionId: await fallback(request), source: 'fallback', jevResult: result }
  }

  async decideBatch(
    state: State,
    decisions: Array<Omit<DecisionRequest, 'state'>>,
    minSelectedProbability?: number,
  ): Promise<DecisionResult[]> {
    const body = await this.post<{ decisions: DecisionResult[] }>('/v1/decide/batch', {
      state,
      decisions,
      ...(minSelectedProbability === undefined
        ? {}
        : { min_selected_probability: minSelectedProbability }),
    })
    return body.decisions
  }

  health(): Promise<{ status: string }> {
    return this.request('/health')
  }

  ready(): Promise<{ status: string; engine: string; model: string }> {
    return this.request('/ready')
  }

  info(): Promise<Record<string, unknown>> {
    return this.request('/v1/info')
  }
}
