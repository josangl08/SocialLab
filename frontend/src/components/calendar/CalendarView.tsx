import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import withDragAndDrop from 'react-big-calendar/lib/addons/dragAndDrop';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import es from 'date-fns/locale/es';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import 'react-big-calendar/lib/addons/dragAndDrop/styles.css';
import './CalendarView.css';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import PostDetailModal from '../posts/PostDetailModal';
import ProposalModal, { type ContentProposal } from './ProposalModal';

interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date: string | null;
}

interface InstagramAccount {
  id: number;
  username: string;
}

interface CalendarViewProps {
  onNewPost?: (date?: string) => void;
  onEdit?: (post: Post) => void;
  refreshSignal?: number;
}

const locales = { 'es': es };
const localizer = dateFnsLocalizer({ format, parse, startOfWeek, getDay, locales });

// Must be created outside the component to avoid re-instantiation on every render.
const DnDCalendar = withDragAndDrop(Calendar as any);

const WEEKDAY_OFFSETS: Record<string, number> = {
  Monday: 0, Tuesday: 1, Wednesday: 2, Thursday: 3,
  Friday: 4, Saturday: 5, Sunday: 6,
};

function proposalToEvents(proposal: ContentProposal): any[] {
  const weekStart = new Date(proposal.week_start);
  return proposal.slots.map((slot, i) => {
    const offset = WEEKDAY_OFFSETS[slot.day] ?? 0;
    const start = new Date(weekStart);
    start.setDate(weekStart.getDate() + offset);
    return {
      id: `proposal-${proposal.id}-${i}`,
      title: `[IA] ${slot.theme}`,
      start,
      end: start,
      allDay: true,
      type: 'proposal' as const,
      resource: proposal,
      className: 'event-proposal',
    };
  });
}

const CalendarView: React.FC<CalendarViewProps> = ({ onNewPost, onEdit, refreshSignal }) => {
  const { token, syncCompleted } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState<any[]>([]);
  const rescheduleInProgress = React.useRef<Set<number>>(new Set());
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [dragError, setDragError] = useState<string | null>(null);
  const dragErrorTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const [tooltip, setTooltip] = useState<{ event: any; x: number; y: number } | null>(null);

  const showDragError = useCallback((message: string) => {
    if (dragErrorTimer.current) clearTimeout(dragErrorTimer.current);
    setDragError(message);
    dragErrorTimer.current = setTimeout(() => setDragError(null), 4000);
  }, []);

  const [refreshKey, setRefreshKey] = useState(0);

  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [currentView, setCurrentView] = useState<string>('month');
  const [showPostModal, setShowPostModal] = useState<boolean>(false);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [showProposalModal, setShowProposalModal] = useState<boolean>(false);
  const [selectedProposal, setSelectedProposal] = useState<ContentProposal | null>(null);

  useEffect(() => {
    const fetchCalendarData = async () => {
      if (!token) {
        setError('No hay token de autenticación disponible.');
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

        const [postsRes, accountsRes] = await Promise.all([
          fetch('http://localhost:8000/api/posts', { headers }),
          fetch('http://localhost:8000/instagram/accounts', { headers }),
        ]);

        if (!postsRes.ok) {
          const err = await postsRes.json();
          setError('Error al cargar publicaciones: ' + (err.detail || 'Error desconocido'));
          return;
        }

        const posts: Post[] = await postsRes.json();
        const postEvents = posts.map(post => {
          const start = post.publication_date
            ? new Date(post.publication_date)
            : post.scheduled_at
            ? new Date(post.scheduled_at)
            : new Date(post.created_at);
          return {
            id: post.id,
            title: post.content.substring(0, 40),
            start,
            end: start,
            allDay: false,
            type: 'post' as const,
            resource: post,
            className: `event-${post.post_type} event-status-${post.status}`,
          };
        });

        let proposalEvents: any[] = [];
        if (accountsRes.ok) {
          const accounts: InstagramAccount[] = await accountsRes.json();
          const proposalFetches = accounts.map(acc =>
            fetch(`http://localhost:8000/api/agent/proposals?account_id=${acc.id}`, { headers })
              .then(r => (r.ok ? r.json() : []))
              .catch(() => [])
          );
          const proposalArrays: ContentProposal[][] = await Promise.all(proposalFetches);
          proposalEvents = proposalArrays
            .flat()
            .filter((p: ContentProposal) => p.status === 'pending_approval')
            .flatMap((p: ContentProposal) => proposalToEvents(p));
        }

        setEvents([...postEvents, ...proposalEvents]);
      } catch (err: any) {
        setError('Error de red o servidor: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchCalendarData();
  }, [token, syncCompleted, refreshKey, refreshSignal]);

  const handleEventDrop = useCallback(
    async ({ event, start }: { event: any; start: Date | string }) => {
      if (event.type !== 'post') return;
      if (rescheduleInProgress.current.has(event.id)) return;

      const targetDate = new Date(start);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (targetDate < today) {
        showDragError('No puedes programar publicaciones en fechas pasadas.');
        return;
      }

      rescheduleInProgress.current.add(event.id);
      const prevEvents = events;
      setEvents(prev =>
        prev.map(e => (e.id === event.id ? { ...e, start: new Date(start), end: new Date(start) } : e))
      );

      try {
        const res = await fetch(`http://localhost:8000/api/scheduler/reschedule/${event.id}`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_scheduled_time: new Date(start).toISOString() }),
        });

        if (!res.ok) {
          setEvents(prevEvents);
          showDragError('No se pudo reprogramar la publicación.');
        }
      } catch {
        setEvents(prevEvents);
        showDragError('Error al reprogramar la publicación.');
      } finally {
        rescheduleInProgress.current.delete(event.id);
      }
    },
    [events, token]
  );

  const handleSelectSlot = useCallback(({ start }: { start: Date | string }) => {
    const isoDate = new Date(start).toISOString();
    if (onNewPost) onNewPost(isoDate);
    else navigate(`/create-post?date=${isoDate}`);
  }, [navigate, onNewPost]);

  const handleSelectEvent = useCallback((event: any) => {
    setTooltip(null);
    if (event.type === 'proposal') {
      setSelectedProposal(event.resource as ContentProposal);
      setShowProposalModal(true);
    } else {
      setSelectedPost(event.resource as Post);
      setShowPostModal(true);
    }
  }, []);

  const handleProposalAction = useCallback(
    (proposalId: string) => {
      setEvents(prev => prev.filter(e => !(e.type === 'proposal' && e.resource.id === proposalId)));
    },
    []
  );

  const eventPropGetter = (event: any) => ({ className: event.className });

  // Stable custom event renderer — captures setTooltip which is a stable React ref
  const EventComponent = useMemo(() => {
    return function CustomCalendarEvent({ event }: { event: any }) {
      return (
        <span
          style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          onMouseEnter={(e) => {
            if (event.resource?.media_url) {
              setTooltip({ event, x: e.clientX, y: e.clientY });
            }
          }}
          onMouseLeave={() => setTooltip(null)}
        >
          {event.title}
        </span>
      );
    };
  }, []);

  if (loading) return (
    <div className="sl-calendar-wrap">
      <div className="sl-cal-loading">
        <div className="sl-cal-spinner"></div>
        Cargando calendario...
      </div>
    </div>
  );

  if (error) return (
    <div className="sl-calendar-wrap">
      <div className="sl-cal-error">
        <i className="bi bi-exclamation-circle"></i>
        {error}
      </div>
    </div>
  );

  return (
    <div className="sl-calendar-wrap">
      <div className="sl-cal-grid-wrap">
        {dragError && (
          <div className="sl-drag-error">
            <i className="bi bi-exclamation-triangle"></i>
            {dragError}
          </div>
        )}
        <DnDCalendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: '100%' }}
          defaultView="month"
          views={['month', 'week', 'day', 'agenda']}
          culture="es"
          selectable
          draggableAccessor={(event: any) => event.type === 'post'}
          onEventDrop={handleEventDrop}
          onSelectSlot={handleSelectSlot}
          onSelectEvent={handleSelectEvent}
          eventPropGetter={eventPropGetter}
          components={{ event: EventComponent }}
          date={currentDate}
          onNavigate={setCurrentDate}
          view={currentView}
          onView={setCurrentView}
          messages={{
            allDay: 'Todo el día',
            previous: 'Anterior',
            next: 'Siguiente',
            today: 'Hoy',
            month: 'Mes',
            week: 'Semana',
            day: 'Día',
            agenda: 'Agenda',
            date: 'Fecha',
            time: 'Hora',
            event: 'Evento',
            noEventsInRange: 'No hay publicaciones en este rango.',
            showMore: (total: number) => `+ ${total} más`,
          }}
        />
      </div>

      <div className="sl-cal-legend">
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot draft"></span>
          Borrador
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot scheduled"></span>
          Programado
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot published"></span>
          Publicado
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot proposal"></span>
          Propuesta IA
        </span>
      </div>

      {tooltip?.event.resource?.media_url && (
        <div
          className="sl-event-tooltip"
          style={{
            left: Math.min(tooltip.x + 18, window.innerWidth - 228),
            top: Math.max(tooltip.y - 90, 10),
          }}
        >
          <img src={tooltip.event.resource.media_url} alt="" className="sl-event-tooltip-img" />
          {tooltip.event.resource.content && (
            <p className="sl-event-tooltip-caption">
              {tooltip.event.resource.content.substring(0, 80)}{tooltip.event.resource.content.length > 80 ? '…' : ''}
            </p>
          )}
        </div>
      )}

      <PostDetailModal
        show={showPostModal}
        onHide={() => { setShowPostModal(false); setSelectedPost(null); }}
        post={selectedPost}
        onEdit={onEdit && selectedPost ? () => { setShowPostModal(false); onEdit(selectedPost); } : undefined}
        onActionSuccess={() => setRefreshKey(k => k + 1)}
      />
      <ProposalModal
        show={showProposalModal}
        onHide={() => { setShowProposalModal(false); setSelectedProposal(null); }}
        proposal={selectedProposal}
        onActionSuccess={(proposalId) => handleProposalAction(proposalId)}
      />
    </div>
  );
};

export default CalendarView;
