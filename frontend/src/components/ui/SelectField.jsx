import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

export const SelectField = ({ name, value, onChange, options }) => {
  const [open, setOpen] = useState(false);
  const fieldRef = useRef(null);

  useEffect(() => {
    const closeOnOutsideClick = (event) => {
      if (!fieldRef.current?.contains(event.target)) setOpen(false);
    };

    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => document.removeEventListener('mousedown', closeOnOutsideClick);
  }, []);

  const selectOption = (nextValue) => {
    onChange({ target: { name, value: nextValue } });
    setOpen(false);
  };

  return (
    <div ref={fieldRef} className="custom-select">
      <button
        type="button"
        className="custom-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{value}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="custom-select-menu" role="listbox">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={value === option.value}
              className={`custom-select-option ${value === option.value ? 'is-selected' : ''}`}
              onClick={() => selectOption(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
