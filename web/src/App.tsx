import { useEffect, useState } from 'react';
import { firstPage, getPage } from '@/core/navigation';
import { navigate, useRoute } from '@/core/router';
import { Icon } from '@/ui/Icon';
import { DialogProvider } from '@/ui/Dialogs';
import { Sidebar } from '@/ui/Sidebar';
import { ToastProvider } from '@/ui/Toasts';

// Every module registers its pages (and file viewers) when imported.
import.meta.glob('./modules/*/index.ts', { eager: true });

function App() {
  const route = useRoute();
  const [menuOpen, setMenuOpen] = useState(false);
  const page = getPage(route.page) ?? firstPage();

  useEffect(() => {
    if (page && route.page !== page.id) navigate(page.id, route.page ? {} : route.params);
  }, [page, route.page, route.params]);

  useEffect(() => {
    document.title = page ? `${page.label} · lazy_bird` : 'lazy_bird';
  }, [page]);

  const Page = page?.component;
  return (
    <ToastProvider>
      <DialogProvider>
      <div className="app-shell">
        <Sidebar current={page?.id ?? ''} open={menuOpen} onNavigate={() => setMenuOpen(false)} />
        {menuOpen && <div className="sidebar-scrim" onClick={() => setMenuOpen(false)} />}
        <div className="main-wrapper">
          <div className="top-bar mobile-only">
            <button type="button" className="btn btn-ghost btn-icon menu-toggle" onClick={() => setMenuOpen(true)} aria-label="Open the menu">
              <Icon name="menu" />
            </button>
            <span className="top-bar-title">{page?.label}</span>
          </div>
          <main className={`content-viewport ${page?.flush ? 'is-flush' : ''}`}>
            {Page ? (
              page.flush ? (
                <Page key={page.id} />
              ) : (
                <div className="content-container">
                  <Page key={page.id} />
                </div>
              )
            ) : (
              <div className="state-empty">No page is installed.</div>
            )}
          </main>
        </div>
      </div>
      </DialogProvider>
    </ToastProvider>
  );
}

export default App;
