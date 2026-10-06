const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/backend';

export interface TraceEvent {
  type: 'thinking' | 'tool_call' | 'tool_result' | 'retry' | 'error' | 'guardrail' | 'planning';
  content: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface ToolResult {
  tool_call_id: string;
  name: string;
  result: string;
  success: boolean;
  duration_ms: number;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  trace: TraceEvent[];
  tool_results: ToolResult[];
  demo_mode: boolean;
}

export interface HealthResponse {
  status: string;
  demo_mode: boolean;
  timestamp: string;
}

export interface SessionHistory {
  session_id: string;
  demo_mode: boolean;
  messages: Array<{
    role: string;
    content: string;
    timestamp: string;
  }>;
  trace: TraceEvent[];
  tool_results: ToolResult[];
}

async function readError(response: Response): Promise<string> {
  const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
  if (typeof error.detail === 'string') {
    return error.detail;
  }
  return 'Request failed';
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error('API health check failed');
  }
  return response.json();
}

export async function sendMessage(
  message: string,
  sessionId?: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function getSessionHistory(sessionId: string): Promise<SessionHistory> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/history`);
  if (!response.ok) {
    throw new Error('Failed to get session history');
  }
  return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete session');
  }
}
