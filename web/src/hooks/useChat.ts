'use client';

import { useState, useCallback } from 'react';
import { sendMessage, TraceEvent, ToolResult, ChatResponse } from '@/lib/api';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  trace?: TraceEvent[];
  toolResults?: ToolResult[];
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [allTrace, setAllTrace] = useState<TraceEvent[]>([]);
  const [allToolResults, setAllToolResults] = useState<ToolResult[]>([]);

  const send = useCallback(async (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response: ChatResponse = await sendMessage(content, sessionId);
      
      setSessionId(response.session_id);
      setDemoMode(response.demo_mode);

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        trace: response.trace,
        toolResults: response.tool_results,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setAllTrace((prev) => [...prev, ...response.trace]);
      setAllToolResults((prev) => [...prev, ...response.tool_results]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const reset = useCallback(() => {
    setMessages([]);
    setSessionId(undefined);
    setError(null);
    setAllTrace([]);
    setAllToolResults([]);
  }, []);

  return {
    messages,
    isLoading,
    error,
    demoMode,
    sessionId,
    allTrace,
    allToolResults,
    send,
    reset,
  };
}
