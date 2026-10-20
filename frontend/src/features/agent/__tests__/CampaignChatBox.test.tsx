import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { CampaignChatBox } from '../CampaignChatBox';
import { apiClient } from '../../../api/client';

// Mock the apiClient module
vi.mock('../../../api/client', () => ({
  apiClient: {
    postStream: vi.fn(),
  },
}));

describe('CampaignChatBox Component', () => {
  const onCampaignUpdatedMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  test('renders empty chat message state initially', () => {
    render(
      <CampaignChatBox
        campaignId="123"
        onCampaignUpdated={onCampaignUpdatedMock}
      />
    );

    expect(screen.getByTestId('campaign-chat-box')).toBeInTheDocument();
    expect(screen.getByText(/¿Quieres ajustar la campaña?/i)).toBeInTheDocument();
  });

  test('sends a message and triggers postStream', async () => {
    apiClient.postStream = vi.fn().mockImplementation((_path, _body, options) => {
      // Simulate sending a stream response
      options.onLine({
        type: 'tool_call',
        tool: 'supabase_update_campaign_focus',
      });
      options.onLine({
        type: 'tool_result',
        tool: 'supabase_update_campaign_focus',
        ok: true,
      });
      options.onLine({
        type: 'done',
        resolved: true,
        message: 'Listo, ajusté el foco.',
      });
      return Promise.resolve();
    });

    render(
      <CampaignChatBox
        campaignId="123"
        onCampaignUpdated={onCampaignUpdatedMock}
      />
    );

    const input = screen.getByPlaceholderText(/Mensaje a Hermes.../i);
    const sendButton = screen.getByTestId('campaign-chat-send-btn');

    fireEvent.change(input, { target: { value: 'Ajusta la semana 2' } });
    fireEvent.click(sendButton);

    expect(screen.getByText('Ajusta la semana 2')).toBeInTheDocument();

    await waitFor(() => {
      expect(apiClient.postStream).toHaveBeenCalledWith(
        '/api/agent/campaign/123/chat',
        { message: 'Ajusta la semana 2' },
        expect.any(Object)
      );
    });
  });

  test('aborts stream on unmount', () => {
    const abortSpy = vi.fn();
    
    class MockAbortController {
      signal = {} as AbortSignal;
      abort = abortSpy;
    }
    
    const originalAbortController = globalThis.AbortController;
    globalThis.AbortController = MockAbortController as any;

    apiClient.postStream = vi.fn().mockImplementation(() => {
      return new Promise(() => {}); // Never resolves to simulate ongoing request
    });

    const { unmount } = render(
      <CampaignChatBox
        campaignId="123"
        onCampaignUpdated={onCampaignUpdatedMock}
      />
    );

    const input = screen.getByPlaceholderText(/Mensaje a Hermes.../i);
    const sendButton = screen.getByTestId('campaign-chat-send-btn');

    fireEvent.change(input, { target: { value: 'test unmount' } });
    fireEvent.click(sendButton);

    unmount();

    expect(abortSpy).toHaveBeenCalled();

    // Restore global
    globalThis.AbortController = originalAbortController;
  });
});
