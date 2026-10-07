// Form fields built from a settings field definition, as the backend sends
// them (SettingField.to_json() in apps/base.py): {key, label, type, opts,
// placeholder, default, min, max, step}. Used by the Global Settings form
// and each app's settings modal.

// The wrapper div (label and input) for one field. The input's id is
// `${idPrefix}${field.key}`, which readFieldValues() looks up.
function buildField(field, value, idPrefix, wrapperClass = 'field') {
  const id = `${idPrefix}${field.key}`;
  const current = value !== undefined && value !== null ? value : (field.default || '');
  let input;
  if (field.type === 'checkbox') {
    // A switch, like the module toggles. A stored value may be a string
    // from before settings had types.
    const on = current === true || current === 'true';
    return el('div', {class: `${wrapperClass} toggle-row`},
      el('label', {class: 'field-label', htmlFor: id}, field.label),
      el('label', {class: 'switch'}, el('input', {type: 'checkbox', id, checked: on}), el('span', {class: 'slider'})));
  }
  if (field.type === 'select') {
    input = el('select', {class: 'input', id},
      ...(field.opts || []).map(opt => el('option', {value: opt, selected: opt === current}, opt)));
  } else if (field.type === 'textarea') {
    input = el('textarea', {class: 'input input-code', id, rows: 8, placeholder: field.placeholder || '', value: current});
  } else {
    // A datetime-local input only takes YYYY-MM-DDTHH:MM.
    const shown = field.type === 'datetime-local' ? String(current).slice(0, 16) : current;
    input = el('input', {
      class: 'input', id, type: field.type || 'text', placeholder: field.placeholder || '',
      min: field.min, max: field.max, step: field.step, value: shown,
    });
  }
  const wrapper = el('div', {class: wrapperClass}, el('label', {class: 'field-label', htmlFor: id}, field.label), input);
  if (field.type === 'textarea') wrapper.classList.add('span2');
  return wrapper;
}

// {key: value} for every field that has an input on the page, as its type:
// a checkbox as true/false, a number as a number ('' when blank, which the
// backend turns into the default). Null, after a warning toast, if a number
// field holds something that isn't one; the backend checks the ranges.
function readFieldValues(fields, idPrefix) {
  const values = {};
  for (const f of fields) {
    const input = document.getElementById(`${idPrefix}${f.key}`);
    if (!input) continue;
    if (f.type === 'checkbox') {
      values[f.key] = input.checked;
    } else if (f.type === 'number') {
      // A browser leaves value blank for text it can't read as a number.
      if (input.validity && input.validity.badInput) {
        showToast(`${f.label} must be a number`, 'warn');
        return null;
      }
      values[f.key] = input.value.trim() === '' ? '' : Number(input.value);
    } else {
      values[f.key] = input.value;
    }
  }
  return values;
}
