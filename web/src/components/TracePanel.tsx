'use client';

import { TraceEvent, ToolResult } from '@/lib/api';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

interface TracePanelProps {
  trace: TraceEvent[];
  toolResults: ToolResult[];
}

const traceTypeConfig: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  thinking: {
    label: 'Thinking',
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    icon: '💭',
  },
  planning: {
    label: 'Planning',
    color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    icon: '📋',
  },
  tool_call: {
    label: 'Tool Call',
    color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    icon: '🔧',
  },
  tool_result: {
    label: 'Result',
    color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    icon: '✅',
  },
  retry: {
    label: 'Retry',
    color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    icon: '🔄',
  },
  error: {
    label: 'Error',
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    icon: '❌',
  },
  guardrail: {
    label: 'Guardrail',
    color: 'bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-400',
    icon: '🛡️',
  },
};

export function TracePanel({ trace, toolResults }: TracePanelProps) {
  if (trace.length === 0 && toolResults.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
        <div className="text-4xl mb-2">🔍</div>
        <p className="text-sm">No trace events yet</p>
        <p className="text-xs mt-1">Send a message to see the agent&apos;s reasoning</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Agent Trace</h3>
          <Badge variant="outline" className="text-xs">
            {trace.length} events
          </Badge>
        </div>
        
        <Separator />

        <div className="space-y-2">
          {trace.map((event, index) => (
            <TraceEventItem key={index} event={event} index={index} />
          ))}
        </div>

        {toolResults.length > 0 && (
          <>
            <Separator className="my-4" />
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Tool Results</h3>
              <Badge variant="outline" className="text-xs">
                {toolResults.length} calls
              </Badge>
            </div>
            <div className="space-y-2 mt-2">
              {toolResults.map((result, index) => (
                <ToolResultItem key={index} result={result} />
              ))}
            </div>
          </>
        )}
      </div>
    </ScrollArea>
  );
}

function TraceEventItem({ event, index }: { event: TraceEvent; index: number }) {
  const config = traceTypeConfig[event.type] || {
    label: event.type,
    color: 'bg-gray-100 text-gray-800',
    icon: '📝',
  };

  return (
    <div className="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
      <div className="flex items-start gap-2">
        <span className="text-lg">{config.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge className={cn('text-xs', config.color)}>
              {config.label}
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              #{index + 1}
            </span>
          </div>
          <p className="text-xs text-foreground/80 break-words">
            {event.content}
          </p>
          {event.metadata?.protocol === 'mcp' && (
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <Badge variant="outline" className="text-[10px] font-mono">
                MCP {String(event.metadata.method ?? 'tools/call')}
              </Badge>
              {typeof event.metadata.transport === 'string' && (
                <Badge variant="outline" className="text-[10px] font-mono">
                  {event.metadata.transport}
                </Badge>
              )}
            </div>
          )}
          {event.metadata && Object.keys(event.metadata).length > 0 && (
            <details className="mt-2">
              <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground">
                Metadata
              </summary>
              <pre className="mt-1 text-[10px] bg-muted p-2 rounded overflow-x-auto">
                {JSON.stringify(event.metadata, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function ToolResultItem({ result }: { result: ToolResult }) {
  return (
    <div className="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
      <div className="flex items-start gap-2">
        <span className="text-lg">{result.success ? '✅' : '❌'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-medium">{result.name}</span>
            <Badge
              variant="outline"
              className={cn(
                'text-[10px]',
                result.success
                  ? 'border-green-500 text-green-600'
                  : 'border-red-500 text-red-600'
              )}
            >
              {result.duration_ms.toFixed(0)}ms
            </Badge>
          </div>
          <details className="mt-1">
            <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground">
              View result
            </summary>
            <pre className="mt-1 text-[10px] bg-muted p-2 rounded overflow-x-auto max-h-40">
              {result.result}
            </pre>
          </details>
        </div>
      </div>
    </div>
  );
}
