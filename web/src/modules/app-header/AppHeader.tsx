import React, { useEffect, useState, useCallback } from 'react';
import { getHealth } from '@/api/endpoints/health';
import type { HealthResponse } from '@/core/types/api';

interface AppHeaderProps {
  onRefreshAll?: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({ onRefreshAll }) => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getHealth();
      setHealth(data);
      if (!data.success && data.error) {
        setError(data.error);
      }
    } catch (err: any) {
      setError(err?.message || 'Impossible de joindre le backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Rafraîchissement périodique toutes les 30s
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const handleManualRefresh = () => {
    fetchHealth();
    onRefreshAll?.();
  };

  return (
    <div className="top-bar">
      <div className="page-heading">
        <span className="page-title">Tableau de bord</span>
        {loading && <span className="spinner" title="Vérification de l'état système..." />}
        {!loading && health?.success && (
          <span className="badge badge-success">
            <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor' }} />
            Système opérationnel
          </span>
        )}
        {!loading && (!health?.success || error) && (
          <span className="badge badge-error">
            <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'currentColor' }} />
            Backend indisponible
          </span>
        )}
        {health?.database_revision && (
          <span className="badge badge-muted" title={`Révision Alembic : ${health.database_revision}`}>
            DB rev: {health.database_revision.slice(0, 7)}
          </span>
        )}
      </div>

      <div className="top-bar-actions">
        {error && (
          <span style={{ fontSize: '0.75rem', color: 'var(--color-error)' }} title={error}>
            {error.length > 50 ? `${error.slice(0, 50)}...` : error}
          </span>
        )}
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleManualRefresh}
          disabled={loading}
          title="Rafraîchir les données de l'application"
        >
          ↻ Actualiser
        </button>
      </div>
    </div>
  );
};
