import { useState } from 'react';
import { ApiError } from '@/api/client';
import { preferences } from '@/api/endpoints/system';
import type { Preferences } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { SettingsForm } from '@/modules/settings-form/SettingsForm';
import { AsyncState } from '@/ui/AsyncState';
import { PageHeader } from '@/ui/PageHeader';
import { changedPreferences } from './changes';
import { useToast } from '@/ui/toastContext';

function load() {
  return Promise.all([preferences.form(), preferences.get()]).then(([form, values]) => ({ form, values }));
}

export function PreferencesPage() {
  const toast = useToast();
  const data = useResource(load, []);
  const [draft, setDraft] = useState<Preferences | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formKey, setFormKey] = useState(0);
  const [restart, setRestart] = useState<string[]>([]);
  const saved = data.data?.values ?? {};
  const changes = draft ? changedPreferences(saved, draft) : {};
  const dirty = Object.keys(changes).length > 0;

  const save = async () => {
    setErrors({});
    try {
      const result = await preferences.update(changes);
      data.setData((current) => (current ? { ...current, values: result.preferences } : current));
      setDraft(null);
      setFormKey((key) => key + 1);
      setRestart(result.restart_required);
      toast.show('Preferences saved');
    } catch (reason) {
      if (reason instanceof ApiError) setErrors(reason.fieldErrors);
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="Preferences"
        description="How lazy_bird behaves: automatic processing, chunk size, file checks and background work."
        actions={
          <>
            <button type="button" className="btn btn-ghost" disabled={!dirty} onClick={() => { setDraft(null); setErrors({}); setFormKey((key) => key + 1); }}>
              Discard
            </button>
            <button type="button" className="btn btn-primary" disabled={!dirty} onClick={save}>
              Save
            </button>
          </>
        }
      />
      {restart.length > 0 && <div className="alert alert-warning">Restart the server to apply: {restart.join(', ')}.</div>}
      <AsyncState {...data} onRetry={data.reload}>
        {({ form }) => (
          <>
            {Object.entries(form).map(([section, { title, kwargs_key }]) => {
              const sectionErrors = Object.fromEntries(
                Object.entries(errors)
                  .filter(([key]) => key.startsWith(`${section}.`))
                  .map(([key, value]) => [key.slice(section.length + 1), value]),
              );
              return (
                <div key={section} className="card">
                  <div className="card-header">
                    <h2 className="card-title">{title}</h2>
                  </div>
                  <div className="card-body">
                    <SettingsForm
                      key={`${section}-${formKey}`}
                      kwargsKey={kwargs_key}
                      values={(draft ?? saved)[section] ?? {}}
                      errors={sectionErrors}
                      onChange={(values) => setDraft((current) => ({ ...(current ?? saved), [section]: { ...saved[section], ...values } }))}
                    />
                  </div>
                </div>
              );
            })}
          </>
        )}
      </AsyncState>
    </>
  );
}
