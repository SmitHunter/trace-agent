'use client';

import { useEffect, useState, useRef } from 'react';
import { useChat } from '@/hooks/useChat';
import { checkHealth } from '@/lib/api';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatInput } from '@/components/ChatInput';
import { TracePanel } from '@/components/TracePanel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

export default function Home() {
  const {
    messages,
    isLoading,
    error,
    demoMode,
    allTrace,
    allToolResults,
    send,
    reset,
  } = useChat();
  
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then(() => {
        if (!cancelled) setApiStatus('online');
      })
      .catch(() => {
        if (!cancelled) setApiStatus('offline');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const exampleQuestions = [
    "What's the weather in Sydney?",
    "Compare weather in Sydney, Melbourne and Brisbane",
    "Give me a 7-day forecast for Perth",
    "Which Australian cities do you support?",
  ];

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-xl">
              🌤️
            </div>
            <div>
              <h1 className="text-lg font-semibold">Trace Agent</h1>
              <p className="text-xs text-muted-foreground">
                MCP-powered AI with visible reasoning
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {demoMode && (
              <Badge variant="secondary" className="text-xs">
                Demo Mode
              </Badge>
            )}
            <Badge
              variant={apiStatus === 'online' ? 'default' : 'destructive'}
              className="text-xs"
            >
              {apiStatus === 'checking' && '⏳ Connecting...'}
              {apiStatus === 'online' && '🟢 API Online'}
              {apiStatus === 'offline' && '🔴 API Offline'}
            </Badge>
            <Button variant="outline" size="sm" onClick={reset}>
              New Chat
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
        {/* Chat panel */}
        <div className="flex min-h-0 flex-1 flex-col">
          <ScrollArea className="flex-1 px-6">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-12">
                <div className="text-6xl mb-4">🌤️</div>
                <h2 className="text-xl font-semibold mb-2">
                  Australian Weather Agent
                </h2>
                <p className="text-sm text-muted-foreground text-center max-w-md mb-6">
                  Ask me about weather conditions, forecasts, and comparisons
                  for Australian cities. Watch the trace panel to see my
                  reasoning!
                </p>
                <div className="grid grid-cols-2 gap-2 max-w-lg">
                  {exampleQuestions.map((question, i) => (
                    <Button
                      key={i}
                      variant="outline"
                      size="sm"
                      className="text-xs h-auto py-2 px-3 text-left whitespace-normal"
                      onClick={() => send(question)}
                      disabled={isLoading}
                    >
                      {question}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="py-4">
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                {isLoading && (
                  <div className="flex items-center gap-2 py-4 text-muted-foreground">
                    <div className="flex space-x-1">
                      <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                      <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                      <div className="h-2 w-2 animate-bounce rounded-full bg-primary" />
                    </div>
                    <span className="text-sm">Agent is thinking...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </ScrollArea>

          {error && (
            <div className="mx-6 mb-2 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="border-t bg-card p-4">
            <ChatInput
              onSend={send}
              disabled={isLoading}
              loading={isLoading}
            />
          </div>
        </div>

        <div className="h-64 border-t bg-muted/30 md:h-auto md:w-96 md:border-l md:border-t-0">
          <TracePanel trace={allTrace} toolResults={allToolResults} />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t bg-card px-6 py-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span>Built with MCP + Open-Meteo API</span>
            <Separator orientation="vertical" className="h-4" />
            <a
              href="https://github.com/SmitHunter/trace-agent"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              View on GitHub
            </a>
          </div>
          <span>Made by Hunter Smith 🇦🇺</span>
        </div>
      </footer>
    </div>
  );
}
