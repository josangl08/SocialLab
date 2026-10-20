import React from 'react';
import type { ReactNode } from 'react';
import Sidebar from './Sidebar';
import './MainLayout.css'; // Para estilos específicos del layout

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="d-flex main-layout-container">
      <Sidebar />
      <main className="content-area p-4 flex-grow-1">
        {children}
      </main>
    </div>
  );
};

export default MainLayout;
