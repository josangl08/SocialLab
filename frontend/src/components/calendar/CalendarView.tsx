import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import withDragAndDrop from 'react-big-calendar/lib/addons/dragAndDrop';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import 'react-big-calendar/lib/addons/dragAndDrop/styles.css';
import './CalendarView.css';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import PostDetailModal from '../posts/PostDetailModal';

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
  is_ai_generated?: boolean;
  drive_file_id?: string | null;
}

interface CalendarViewProps {
  onNewPost?: (date?: string) => void;
  onEdit?: (post: Post) => void;
  refreshSignal?: number;
  onFocusProposalPost?: (postId: number) => void;
  onDragSuccess?: () => void;
}

const locales = { 'en-US': enUS };
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { weekStartsOn: 1 }),
  getDay,
  locales,
});

// Must be created outside the component to avoid re-instantiation on every render.
const DnDCalendar = withDragAndDrop(Calendar as any);

const CalendarView: React.FC<CalendarViewProps> = ({ onNewPost, onEdit, refreshSignal, onFocusProposalPost, onDragSuccess }) => {
  const { token, syncCompleted } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState<any[]>([]);
  const rescheduleInProgress = React.useRef<Set<number>>(new Set());
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [dragError, setDragError] = useState<string | null>(null);
  const dragErrorTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasLoaded = React.useRef(false);
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
  useEffect(() => {
    const fetchCalendarData = async () => {
      if (!token) {
        setError('No authentication token available.');
        setLoading(false);
        return;
      }

      if (!hasLoaded.current) setLoading(true);
      try {
        const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

        const postsRes = await fetch('http://localhost:8000/api/posts', { headers });

        if (!postsRes.ok) {
          const err = await postsRes.json();
          setError('Error loading posts: ' + (err.detail || 'Unknown error'));
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
            className: post.is_ai_generated && post.status === 'draft'
              ? `event-${post.post_type} event-proposal`
              : `event-${post.post_type} event-status-${post.status}`,
          };
        });

        setEvents(postEvents);
      } catch (err: any) {
        setError('Network or server error: ' + err.message);
      } finally {
        hasLoaded.current = true;
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
        showDragError('Cannot schedule posts in the past.');
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
          showDragError('Could not reschedule the post.');
        } else {
          onDragSuccess?.();
        }
      } catch {
        setEvents(prevEvents);
        showDragError('Network error rescheduling post.');
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
    setSelectedPost(event.resource as Post);
    setShowPostModal(true);
  }, []);

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
        Loading calendar...
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
          culture="en-US"
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
            allDay: 'All day',
            previous: 'Previous',
            next: 'Next',
            today: 'Today',
            month: 'Month',
            week: 'Week',
            day: 'Day',
            agenda: 'Agenda',
            date: 'Date',
            time: 'Time',
            event: 'Event',
            noEventsInRange: 'No posts in this range.',
            showMore: (total: number) => `+${total} more`,
          }}
        />
      </div>

      <div className="sl-cal-legend">
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot proposal"></span>
          AI Proposal
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot draft"></span>
          Draft
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot scheduled"></span>
          Scheduled
        </span>
        <span className="sl-cal-legend-item">
          <span className="sl-cal-legend-dot published"></span>
          Published
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
        onViewProposal={selectedPost?.is_ai_generated && onFocusProposalPost
          ? () => { setShowPostModal(false); setSelectedPost(null); onFocusProposalPost(selectedPost.id); }
          : undefined}
      />
    </div>
  );
};

export default CalendarView;
