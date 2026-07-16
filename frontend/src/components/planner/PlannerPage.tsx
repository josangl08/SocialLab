import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import CalendarView from '../calendar/CalendarView';
import PostList from '../posts/PostList';
import CreatePost from '../posts/CreatePost';
import EditPostForm from '../posts/EditPostForm';
import WeeklyProposalPanel from './WeeklyProposalPanel';
import { MonthlyFocusBanner } from './MonthlyFocusBanner';
import { useAuth } from '../../context/AuthContext';
import './PlannerPage.css';

interface EditablePost {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date?: string | null;
}

const PlannerPage: React.FC = () => {
  const { token } = useAuth();
  const [view, setView]               = useState<'calendar' | 'list'>('calendar');
  const [showDrawer, setShowDrawer]   = useState(false);
  const [drawerDate, setDrawerDate]   = useState('');
  const [editingPost, setEditingPost] = useState<EditablePost | null>(null);
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
  const agentSyncBeforeRef = useRef<string | null>(null);

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

    const authHeaders = { Authorization: `Bearer ${token}` };
    try {
      const [accRes, propRes] = await Promise.all([
        fetch('http://localhost:8000/instagram/accounts', { headers: authHeaders }),
        fetch(`http://localhost:8000/api/agent/proposals?account_id=${primaryAccountId}`, { headers: authHeaders }),
      ]);
      if (accRes.ok) {
        const accounts = await accRes.json();
        const acc = accounts.find((a: { id: number; last_agent_sync?: string }) => a.id === primaryAccountId);
        agentSyncBeforeRef.current = acc?.last_agent_sync ?? null;
      }
      if (propRes.ok) {
        const proposals = await propRes.json();
        proposalCountRef.current = proposals.filter((p: { status: string }) => p.status === 'pending_approval').length;
      }
    } catch { /* proceed with trigger even if pre-fetch fails */ }

    try {
      const res = await fetch('http://localhost:8000/api/agent/trigger', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: primaryAccountId }),
      });
      if (res.ok) {
        setIsAgentRunning(true);
        setAgentStartedAt(Date.now());
      } else if (res.status === 503) {
        setIsDriveError(true);
      } else {
        const body = await res.json().catch(() => ({}));
        setAiStatus(body.detail ?? 'Error al iniciar el agente. Intenta de nuevo.');
      }
    } finally {
      setAiTriggering(false);
    }
  }, [token, aiTriggering, isAgentRunning, primaryAccountId]);

  const openDrawer = useCallback((date?: string) => {
    setEditingPost(null);
    setDrawerDate(date ?? '');
    setShowDrawer(true);
  }, []);

  const openEditDrawer = useCallback((post: EditablePost) => {
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
    fetch('http://localhost:8000/instagram/accounts', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => (r.ok ? r.json() : []))
      .then((accounts: { id: number }[]) => {
        if (accounts.length > 0) setPrimaryAccountId(accounts[0].id);
      })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!isAgentRunning || !token || !primaryAccountId) return;

    const authHeaders = { Authorization: `Bearer ${token}` };

    const poll = async () => {
      try {
        const propRes = await fetch(
          `http://localhost:8000/api/agent/proposals?account_id=${primaryAccountId}`,
          { headers: authHeaders }
        );
        if (propRes.ok) {
          const proposals = await propRes.json();
          const pendingCount = proposals.filter((p: { status: string }) => p.status === 'pending_approval').length;
          if (pendingCount > proposalCountRef.current) {
            setCalendarSignal(k => k + 1);
            stopPolling();
            return;
          }
        }

        const accRes = await fetch('http://localhost:8000/instagram/accounts', { headers: authHeaders });
        if (accRes.ok) {
          const accounts = await accRes.json();
          const account = accounts.find((a: { id: number; last_agent_sync?: string }) => a.id === primaryAccountId);
          if (account?.last_agent_sync && account.last_agent_sync !== agentSyncBeforeRef.current) {
            setAiStatus('No new images in Drive. Add photos to your folder to generate a proposal.');
            stopPolling();
          }
        }
      } catch { /* ignore transient errors */ }
    };

    pollRef.current = setInterval(poll, 15_000);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [isAgentRunning, token, primaryAccountId, stopPolling]);

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
          <button className="planner-new-btn" onClick={() => openDrawer()}>
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
                onNewPost={openDrawer}
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

      {/* ── Create / Edit drawer ─────────────── */}
      {showDrawer && (
        <div className="planner-drawer-backdrop" onClick={closeDrawer}>
          <div className="planner-drawer" onClick={e => e.stopPropagation()}>
            <div className="planner-drawer-header">
              <span className="planner-drawer-title">
                <i className={`bi ${editingPost ? 'bi-pencil-square' : 'bi-plus-circle'}`}></i>
                {editingPost ? 'Edit post' : 'New Post'}
              </span>
              <button className="planner-drawer-close" onClick={closeDrawer} aria-label="Close">
                <i className="bi bi-x-lg"></i>
              </button>
            </div>
            <div className="planner-drawer-body">
              {editingPost ? (
                <EditPostForm
                  post={editingPost as any}
                  onSave={() => { closeDrawer(); setCalendarSignal(k => k + 1); }}
                  onCancel={closeDrawer}
                />
              ) : (
                <CreatePost
                  key={drawerDate}
                  initialDate={drawerDate || undefined}
                  onPostCreated={closeDrawer}
                  onCancel={closeDrawer}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlannerPage;
