import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import CalendarView from '../calendar/CalendarView';
import PostList from '../posts/PostList';
import EditPostForm from '../posts/EditPostForm';
import WeeklyProposalPanel from './WeeklyProposalPanel';
import { MonthlyFocusBanner } from './MonthlyFocusBanner';
import { useAuth } from '../../context/AuthContext';
import { apiClient, ApiError } from '../../api/client';
import type { Post, InstagramAccount, ContentProposal, AgentLog } from '../../types';
import './PlannerPage.css';

const PlannerPage: React.FC = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [view, setView]               = useState<'calendar' | 'list'>('calendar');
  const [showDrawer, setShowDrawer]   = useState(false);
  const [editingPost, setEditingPost] = useState<Post | null>(null);
  const [calendarSignal, setCalendarSignal] = useState(0);
  const [aiTriggering, setAiTriggering] = useState(false);
  const [aiStatus, setAiStatus] = useState<string | null>(null);
  const [primaryAccountId, setPrimaryAccountId] = useState<number | null>(null);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const [agentStartedAt, setAgentStartedAt] = useState<number | null>(null);
  const [isDriveError, setIsDriveError] = useState(false);
  const [focusPostId, setFocusPostId] = useState<number | null>(null);
  const plannerViewDate = useMemo(() => new Date(), []);
  const proposalPanelRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const proposalCountRef = useRef<number>(0);

  const handleFocusProposalPost = useCallback((postId: number) => {
    setFocusPostId(postId);
    setTimeout(() => proposalPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setIsAgentRunning(false);
    setAgentStartedAt(null);
  }, []);

  // Passive 30s sync so bot changes appear in UI without manual reload
  useEffect(() => {
    const id = setInterval(() => setCalendarSignal(k => k + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  const handleProposalsFound = useCallback(() => stopPolling(), [stopPolling]);

  const triggerAiPlan = useCallback(async () => {
    if (!token || aiTriggering || isAgentRunning || !primaryAccountId) return;
    setAiTriggering(true);
    setAiStatus(null);
    setIsDriveError(false);

    try {
      const proposals = await apiClient.get<ContentProposal[]>(`/api/agent/proposals?account_id=${primaryAccountId}`);
      proposalCountRef.current = proposals.filter(p => p.status === 'pending_approval').length;
    } catch { /* proceed with trigger even if pre-fetch fails */ }

    try {
      await apiClient.post('/api/agent/trigger', { account_id: primaryAccountId });
      setIsAgentRunning(true);
      setAgentStartedAt(Date.now());
    } catch (error) {
      if (error instanceof ApiError && error.status === 503) {
        setIsDriveError(true);
      } else {
        setAiStatus(error instanceof ApiError ? error.detail : 'Error al iniciar el agente. Intenta de nuevo.');
      }
    } finally {
      setAiTriggering(false);
    }
  }, [token, aiTriggering, isAgentRunning, primaryAccountId]);

  const openNewPost = useCallback((date?: string) => {
    navigate(`/generate${date ? `?date=${encodeURIComponent(date)}` : ''}`);
  }, [navigate]);

  const openEditDrawer = useCallback((post: Post) => {
    setEditingPost(post);
    setShowDrawer(true);
  }, []);

  const closeDrawer = useCallback(() => {
    setShowDrawer(false);
    setEditingPost(null);
  }, []);

  useEffect(() => {
    if (!showDrawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeDrawer(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showDrawer, closeDrawer]);

  useEffect(() => {
    document.body.style.overflow = showDrawer ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [showDrawer]);

  useEffect(() => {
    if (!token) return;
    apiClient.get<InstagramAccount[]>('/instagram/accounts')
      .then(accounts => {
        if (accounts.length > 0) setPrimaryAccountId(accounts[0].id);
      })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!isAgentRunning || !token || !primaryAccountId || !agentStartedAt) return;

    const poll = async () => {
      try {
        const proposals = await apiClient.get<ContentProposal[]>(
          `/api/agent/proposals?account_id=${primaryAccountId}`
        );
        const pendingCount = proposals.filter(p => p.status === 'pending_approval').length;
        if (pendingCount > proposalCountRef.current) {
          setCalendarSignal(k => k + 1);
          stopPolling();
          return;
        }

        const latestLog = await apiClient.get<AgentLog | null>(
          `/api/agent/logs/latest?account_id=${primaryAccountId}`
        );
        if (latestLog && new Date(latestLog.run_at).getTime() >= agentStartedAt) {
          setAiStatus(
            latestLog.error
              ? `The agent failed: ${latestLog.error}`
              : 'No new images in Drive. Add photos to your folder to generate a proposal.'
          );
          stopPolling();
        }
      } catch { /* ignore transient errors */ }
    };

    pollRef.current = setInterval(poll, 15_000);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [isAgentRunning, token, primaryAccountId, agentStartedAt, stopPolling]);

  useEffect(() => {
    if (!agentStartedAt) return;
    const id = setTimeout(stopPolling, 3 * 60 * 1000);
    return () => clearTimeout(id);
  }, [agentStartedAt, stopPolling]);

  return (
    <div className="planner-page">
      {/* ── Tab bar ─────────────────────────── */}
      <div className="planner-header">
        <div className="planner-tabs">
          <button
            className={`planner-tab${view === 'calendar' ? ' active' : ''}`}
            onClick={() => setView('calendar')}
          >
            <i className="bi bi-calendar-event"></i>
            Calendar
          </button>
          <button
            className={`planner-tab${view === 'list' ? ' active' : ''}`}
            onClick={() => setView('list')}
          >
            <i className="bi bi-grid-3x3"></i>
            Posts
          </button>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {isAgentRunning && (
            <span className="d-flex align-items-center gap-2" style={{ fontSize: '12px', color: 'var(--sl-purple-light)' }}>
              <span className="spinner-border spinner-border-sm" role="status" style={{ width: '12px', height: '12px', borderWidth: '2px', color: 'var(--sl-purple-light)' }} />
              Generating proposal...
            </span>
          )}
          {aiStatus && (
            <span style={{ fontSize: '12px', color: '#f87171', maxWidth: '280px' }}>
              {aiStatus}
            </span>
          )}
          <button
            className="planner-new-btn"
            onClick={triggerAiPlan}
            disabled={aiTriggering || isAgentRunning || !primaryAccountId}
            style={{ background: 'rgba(139, 92, 246, 0.15)', borderColor: 'rgba(139, 92, 246, 0.4)', opacity: (aiTriggering || isAgentRunning || !primaryAccountId) ? 0.6 : 1 }}
          >
            <i className={`bi ${(aiTriggering || isAgentRunning) ? 'bi-hourglass-split' : 'bi-stars'}`}></i>
            {aiTriggering ? 'Starting...' : isAgentRunning ? 'In progress...' : 'Generate AI Plan'}
          </button>
          <button className="planner-new-btn" onClick={() => openNewPost()}>
            <i className="bi bi-plus-lg"></i>
            New Post
          </button>
        </div>
      </div>

      {/* ── Drive error banner ──────────────── */}
      {isDriveError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
          padding: '12px 24px',
          background: 'rgba(239, 68, 68, 0.1)',
          borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171', fontSize: '13px',
        }}>
          <i className="bi bi-exclamation-triangle-fill" style={{ flexShrink: 0 }} />
          <span>Google Drive is not connected. The AI agent cannot access your images.</span>
          <Link
            to="/settings"
            style={{ color: '#a78bfa', fontWeight: 600, marginLeft: 'auto', textDecoration: 'none', whiteSpace: 'nowrap' }}
          >
            Connect Drive in Settings →
          </Link>
          <button
            onClick={() => setIsDriveError(false)}
            style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '16px', padding: '0 4px', flexShrink: 0 }}
            aria-label="Dismiss"
          >
            <i className="bi bi-x-lg" />
          </button>
        </div>
      )}

      {/* ── Content ─────────────────────────── */}
      <div className="planner-content">
        {view === 'calendar'
          ? (
            <>
              <MonthlyFocusBanner accountId={primaryAccountId} currentDate={plannerViewDate} />
              <CalendarView
                onNewPost={openNewPost}
                onEdit={openEditDrawer}
                refreshSignal={calendarSignal}
                onFocusProposalPost={handleFocusProposalPost}
                onDragSuccess={() => setCalendarSignal(k => k + 1)}
              />
              <div ref={proposalPanelRef}>
                <WeeklyProposalPanel
                  accountId={primaryAccountId}
                  refreshSignal={calendarSignal}
                  onProposalAction={() => setCalendarSignal(k => k + 1)}
                  onProposalsFound={isAgentRunning ? handleProposalsFound : undefined}
                  focusPostId={focusPostId}
                  onFocusHandled={() => setFocusPostId(null)}
                />
              </div>
            </>
          )
          : <PostList />
        }
      </div>

      {/* ── Edit drawer ─────────────── */}
      {showDrawer && editingPost && (
        <div className="planner-drawer-backdrop" onClick={closeDrawer}>
          <div className="planner-drawer" onClick={e => e.stopPropagation()}>
            <div className="planner-drawer-header">
              <span className="planner-drawer-title">
                <i className="bi bi-pencil-square"></i>
                Edit post
              </span>
              <button className="planner-drawer-close" onClick={closeDrawer} aria-label="Close">
                <i className="bi bi-x-lg"></i>
              </button>
            </div>
            <div className="planner-drawer-body">
              <EditPostForm
                post={editingPost}
                onSave={() => { closeDrawer(); setCalendarSignal(k => k + 1); }}
                onCancel={closeDrawer}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlannerPage;
