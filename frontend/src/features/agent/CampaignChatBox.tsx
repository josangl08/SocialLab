import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../../api/client';
import type { MonthlyCampaign } from '../../types';
import './CampaignChatBox.css';

export interface CampaignChatBoxProps {
  campaignId: string;
  onCampaignUpdated: (campaign: MonthlyCampaign) => void;
  accountId?: number;
  monthDate?: string;
}

export interface StreamLine {
  type: 'tool_call' | 'tool_result' | 'done';
  tool?: string;
  ok?: boolean;
  resolved?: boolean;
  message?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  isStreaming?: boolean;
  toolCalls?: {
    tool: string;
    status: 'running' | 'success' | 'error';
  }[];
}

export const CampaignChatBox: React.FC<CampaignChatBoxProps> = ({
  campaignId,
  onCampaignUpdated,
  accountId,
  monthDate,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Scroll to bottom on new messages
  const scrollToBottom = () => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Clean up any pending stream on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessageText = inputValue.trim();
    setInputValue('');
    setError(null);
    setIsLoading(true);

    // Add user message to list
    const userMsgId = Math.random().toString(36).substring(7);
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: 'user', text: userMessageText },
    ]);

    // Stub for postStream - logic will be implemented by [logic] task
    // But we provide the scaffold of abort signal and callback setup
    try {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      const assistantMsgId = Math.random().toString(36).substring(7);
      
      // We start a placeholder message for the assistant stream
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          sender: 'assistant',
          text: '',
          isStreaming: true,
          toolCalls: [],
        },
      ]);

      const updateAssistantMessage = (updater: (msg: ChatMessage) => ChatMessage) => {
        setMessages((prev) => {
          const idx = prev.findIndex((m) => m.id === assistantMsgId);
          if (idx === -1) return prev;
          const updated = [...prev];
          updated[idx] = updater(updated[idx]);
          return updated;
        });
      };

      await apiClient.postStream<StreamLine>(
        `/api/agent/campaign/${campaignId}/chat`,
        { message: userMessageText },
        {
          signal: abortControllerRef.current.signal,
          onLine: (line) => {
            if (line.type === 'tool_call' && line.tool) {
              const tool = line.tool;
              updateAssistantMessage((msg) => ({
                ...msg,
                toolCalls: [...(msg.toolCalls ?? []), { tool, status: 'running' }],
              }));
            } else if (line.type === 'tool_result' && line.tool) {
              const tool = line.tool;
              const ok = line.ok;
              updateAssistantMessage((msg) => ({
                ...msg,
                toolCalls: (msg.toolCalls ?? []).map((tc) =>
                  tc.tool === tool && tc.status === 'running'
                    ? { ...tc, status: ok ? 'success' : 'error' }
                    : tc
                ),
              }));
            } else if (line.type === 'done') {
              updateAssistantMessage((msg) => ({
                ...msg,
                text: line.message ?? '',
                isStreaming: false,
              }));

              if (line.resolved && accountId && monthDate) {
                apiClient
                  .get<MonthlyCampaign | null>(
                    `/api/agent/campaign?account_id=${accountId}&month_date=${monthDate}`
                  )
                  .then((updatedCampaign) => {
                    if (updatedCampaign) onCampaignUpdated(updatedCampaign);
                  })
                  .catch(() => {
                    // Chat already confirmed the change; a failed refresh just means
                    // the drawer form stays stale until the next reopen.
                  });
              }
            }
          },
        }
      );

    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Error al enviar mensaje');
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="campaign-chat-box" data-testid="campaign-chat-box">
      <div className="campaign-chat-header">
        <div className="d-flex align-items-center">
          <i className="bi bi-robot me-2 text-primary"></i>
          <span className="fw-bold">Ajustes con Hermes</span>
        </div>
        <small className="text-muted">Pregúntale para cambiar el foco o los hitos</small>
      </div>

      <div className="campaign-chat-messages">
        {messages.length === 0 ? (
          <div className="campaign-chat-empty">
            <p className="mb-1 text-white-50">¿Quieres ajustar la campaña?</p>
            <small className="text-muted">
              Pídele a Hermes cosas como: "Cambia el foco de la semana 2 para hablar del lanzamiento" o "Agrega un hito el día 15".
            </small>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.sender}`}>
              <div className="chat-message-avatar">
                {msg.sender === 'user' ? (
                  <i className="bi bi-person-fill"></i>
                ) : (
                  <i className="bi bi-robot text-primary"></i>
                )}
              </div>
              <div className="chat-message-content">
                {msg.text && <div className="chat-message-text">{msg.text}</div>}
                
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="chat-message-tool-calls mt-2">
                    {msg.toolCalls.map((tc, idx) => (
                      <div key={idx} className={`tool-call-status ${tc.status}`}>
                        {tc.status === 'running' && (
                          <span className="spinner-border spinner-border-sm me-1 text-primary" role="status" />
                        )}
                        {tc.status === 'success' && <i className="bi bi-check-circle-fill text-success me-1"></i>}
                        {tc.status === 'error' && <i className="bi bi-x-circle-fill text-danger me-1"></i>}
                        <small className="text-muted">
                          {tc.tool === 'supabase_update_campaign_focus' && 'Actualizando foco semanal...'}
                          {tc.tool === 'supabase_update_campaign_milestones' && 'Actualizando hitos...'}
                          {tc.tool === 'supabase_update_campaign_details' && 'Actualizando detalles de campaña...'}
                          {!['supabase_update_campaign_focus', 'supabase_update_campaign_milestones', 'supabase_update_campaign_details'].includes(tc.tool || '') && `Ejecutando ${tc.tool}...`}
                        </small>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {error && (
          <div className="alert alert-danger mx-3 my-2 py-2 px-3 small d-flex align-items-center">
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            <div>{error}</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSendMessage} className="campaign-chat-input-area border-top p-2 bg-dark">
        <div className="input-group">
          <input
            type="text"
            className="form-control bg-dark border-secondary text-white"
            placeholder="Mensaje a Hermes..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isLoading}
            data-testid="campaign-chat-input"
          />
          <button
            type="submit"
            className="btn btn-primary d-flex align-items-center justify-content-center"
            disabled={isLoading || !inputValue.trim()}
            data-testid="campaign-chat-send-btn"
          >
            {isLoading ? (
              <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
            ) : (
              <i className="bi bi-send-fill" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
