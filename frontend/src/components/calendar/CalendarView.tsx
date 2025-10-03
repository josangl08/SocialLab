import React, { useState, useEffect } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import es from 'date-fns/locale/es';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import './CalendarView.css';
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

const CalendarView: React.FC = () => {
  const { token, syncCompleted } = useAuth(); // Añadir syncCompleted
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [currentView, setCurrentView] = useState<string>('month');
  const [showModal, setShowModal] = useState<boolean>(false);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);

  useEffect(() => {
    const fetchPostsForCalendar = async () => {
      if (!token) {
        setError('No hay token de autenticación disponible.');
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const response = await fetch('http://localhost:8000/posts', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data: Post[] = await response.json();
          const calendarEvents = data.map(post => {
            const start = post.publication_date ? new Date(post.publication_date) : (post.scheduled_at ? new Date(post.scheduled_at) : new Date(post.created_at));
            const end = start;
            return {
              id: post.id,
              title: `[${post.status.toUpperCase()}] ${post.content.substring(0, 50)}...`,
              start: start,
              end: end,
              allDay: false,
              resource: post,
              className: `event-${post.post_type} event-status-${post.status}`
            };
          });
          setEvents(calendarEvents);
        } else {
          const errorData = await response.json();
          setError('Error al cargar publicaciones para el calendario: ' + (errorData.detail || 'Error desconocido'));
        }
      } catch (err: any) {
        setError('Error de red o servidor: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPostsForCalendar();
  }, [token, syncCompleted]); // Volver a cargar si syncCompleted cambia

  const eventPropGetter = (event: any) => {
    return { className: event.className };
  };

  const handleNavigate = (newDate: Date) => {
    setCurrentDate(newDate);
  };

  const handleViewChange = (newView: string) => {
    setCurrentView(newView);
  };

  const handleSelectEvent = (event: any) => {
    setSelectedPost(event.resource);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedPost(null);
  };

  if (loading) {
    return <p className="text-center text-primary">Cargando calendario...</p>;
  }

  if (error) {
    return <p className="text-danger">{error}</p>;
  }

  return (
    <div className="p-4">
      <h3 className="mb-4 text-primary">Calendario de Publicaciones</h3>
      <div style={{ height: '700px' }}>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: '100%' }}
          defaultView="month"
          views={['month', 'week', 'day', 'agenda']}
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
            showMore: (total) => `+ ${total} más`,
          }}
          eventPropGetter={eventPropGetter}
          date={currentDate}
          onNavigate={handleNavigate}
          view={currentView}
          onView={handleViewChange}
          onSelectEvent={handleSelectEvent}
        />
      </div>
      <PostDetailModal show={showModal} onHide={handleCloseModal} post={selectedPost} />
    </div>
  );
};

export default CalendarView;