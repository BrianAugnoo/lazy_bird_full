import { useState } from 'react';
import { Icon } from '@/ui/Icon';
import { addLanguage, moveLanguage } from './userForm';

/** Languages from the best mastered to the least, reordered with the arrows. */
export function LanguageList({ value, onChange }: { value: string[]; onChange: (languages: string[]) => void }) {
  const [text, setText] = useState('');

  const add = () => {
    onChange(addLanguage(value, text));
    setText('');
  };

  return (
    <div className="stack-sm">
      {value.map((language, index) => (
        <div key={language} className="language-row">
          <span className="muted">{index + 1}.</span>
          <span>{language}</span>
          <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={`Move ${language} up`} disabled={index === 0} onClick={() => onChange(moveLanguage(value, index, -1))}>
            ↑
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-icon btn-sm"
            aria-label={`Move ${language} down`}
            disabled={index === value.length - 1}
            onClick={() => onChange(moveLanguage(value, index, 1))}
          >
            ↓
          </button>
          <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={`Remove ${language}`} onClick={() => onChange(value.filter((item) => item !== language))}>
            <Icon name="close" />
          </button>
        </div>
      ))}
      <div className="language-row">
        <input
          className="form-input"
          value={text}
          aria-label="Add a language"
          placeholder={value.length === 0 ? 'e.g. French' : 'Another language'}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              add();
            }
          }}
        />
        <button type="button" className="btn btn-secondary btn-sm" disabled={!text.trim()} onClick={add}>
          Add
        </button>
      </div>
    </div>
  );
}
