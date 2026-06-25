import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CalendarView from '../calendar/CalendarView';
import PostList from '../posts/PostList';

const PlannerPage: React.FC = () => {
  const [view, setView] = useState<'calendar' | 'list'>('calendar');
  const navigate = useNavigate();

  return (
    <div className="container py-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <ul className="nav nav-pills">
          <li className="nav-item">
            <button
              className={`nav-link ${view === 'calendar' ? 'active' : ''}`}
              onClick={() => setView('calendar')}
              style={{ cursor: 'pointer' }}
            >
              <i className="bi bi-calendar-event me-2"></i>
              Calendario
            </button>
          </li>
          <li className="nav-item">
            <button
              className={`nav-link ${view === 'list' ? 'active' : ''}`}
              onClick={() => setView('list')}
              style={{ cursor: 'pointer' }}
            >
              <i className="bi bi-list-ul me-2"></i>
              Lista de Publicaciones
            </button>
          </li>
        </ul>
        <button
          className="btn btn-primary"
          onClick={() => navigate('/create-post')}
        >
          <i className="bi bi-plus-circle me-2"></i>
          + Nueva Publicación
        </button>
      </div>

      <div className="planner-content">
        {view === 'calendar' ? <CalendarView /> : <PostList />}
      </div>
    </div>
  );
};

export default PlannerPage;
