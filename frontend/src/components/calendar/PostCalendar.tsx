import React, { useState, useEffect } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import es from 'date-fns/locale/es';
import 'bootstrap-icons/font/bootstrap-icons.css';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import './PostCalendar.css';

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

interface CalendarEvent {
  id: number;
  title: string;
  start: Date;
  end: Date;
  allDay: boolean;
  resource: Post;
  className: string;
}

const locales = {
  'es': es,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

const PostCalendar: React.FC = () => {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [showModal, setShowModal] = useState<boolean>(false);

  useEffect(() => {
    fetchPostsForCalendar();
  }, []);

  const fetchPostsForCalendar = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/posts', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const posts: Post[] = data.posts || [];

        const calendarEvents: CalendarEvent[] = posts.map(post => {
          const start = post.publication_date
            ? new Date(post.publication_date)
            : (post.scheduled_at ? new Date(post.scheduled_at) : new Date(post.created_at));

          return {
            id: post.id,
            title: post.content.substring(0, 45) + '...',
            start: start,
            end: start,
            allDay: false,
            resource: post,
            className: `event-${post.status}`
          };
        });

        setEvents(calendarEvents);
      }
    } catch (error) {
      console.error('Error fetching posts for calendar:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string): JSX.Element => {
    switch (status) {
      case 'published': return <i className="bi bi-check-circle-fill"></i>;
      case 'scheduled': return <i className="bi bi-calendar-check"></i>;
      case 'draft': return <i className="bi bi-pencil-square"></i>;
      default: return <i className="bi bi-file-text"></i>;
    }
  };

  const eventStyleGetter = (event: CalendarEvent) => {
    let backgroundColor = '#667eea';

    switch (event.resource.status) {
      case 'published':
        backgroundColor = '#10b981';
        break;
      case 'scheduled':
        backgroundColor = '#667eea';
        break;
      case 'draft':
        backgroundColor = '#94a3b8';
        break;
    }

    return {
      style: {
        backgroundColor,
        borderRadius: '5px',
        opacity: 0.9,
        color: 'white',
        border: '0',
        display: 'block',
        fontWeight: '500',
        fontSize: '0.875rem'
      }
    };
  };

  const handleSelectEvent = (event: CalendarEvent) => {
    setSelectedPost(event.resource);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedPost(null);
  };

  if (loading) {
    return (
      <div className="calendar-loading">
        <div className="spinner"></div>
        <p>Cargando calendario...</p>
      </div>
    );
  }

  return (
    <div className="post-calendar">
      <div className="calendar-header">
        <h2><i className="bi bi-calendar-event me-2"></i>Calendario de Publicaciones</h2>
        <p className="calendar-description">
          Visualiza tus posts programados, borradores y publicaciones
        </p>
      </div>

      <div className="calendar-legend">
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#10b981' }}></span>
          <span><i className="bi bi-check-circle-fill me-1"></i>Publicado</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#667eea' }}></span>
          <span><i className="bi bi-calendar-check me-1"></i>Programado</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#94a3b8' }}></span>
          <span><i className="bi bi-pencil-square me-1"></i>Borrador</span>
        </div>
      </div>

      <div className="calendar-wrapper">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 600 }}
          culture="es"
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
            showMore: (total) => `+ Ver ${total} más`,
          }}
          eventPropGetter={eventStyleGetter}
          onSelectEvent={handleSelectEvent}
        />
      </div>

      {/* Modal for Post Details */}
      {showModal && selectedPost && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Detalles de la Publicación</h3>
              <button className="modal-close" onClick={handleCloseModal}>×</button>
            </div>

            <div className="modal-body">
              <div className="post-detail-item">
                <label>Estado:</label>
                <span className={`status-badge status-${selectedPost.status}`}>
                  {getStatusIcon(selectedPost.status)} {selectedPost.status.toUpperCase()}
                </span>
              </div>

              {selectedPost.media_url && (
                <div className="post-detail-item">
                  <label>Imagen:</label>
                  <img
                    src={selectedPost.media_url}
                    alt="Post preview"
                    className="modal-image"
                  />
                </div>
              )}

              <div className="post-detail-item">
                <label>Caption:</label>
                <p className="post-caption">{selectedPost.content}</p>
              </div>

              {selectedPost.scheduled_at && (
                <div className="post-detail-item">
                  <label>Fecha programada:</label>
                  <p>{new Date(selectedPost.scheduled_at).toLocaleString('es-ES')}</p>
                </div>
              )}

              <div className="post-detail-item">
                <label>Creado:</label>
                <p>{new Date(selectedPost.created_at).toLocaleString('es-ES')}</p>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={handleCloseModal}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PostCalendar;
