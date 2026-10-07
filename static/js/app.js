// Live split preview on the add-expense form (equal + custom modes).
(function () {
  const amountEl = document.getElementById('id_amount');
  const preview = document.getElementById('split-preview');
  if (!amountEl || !preview) return;

  const customWrap = document.getElementById('custom-shares');
  const form = amountEl.closest('form');
  const SYMBOL = (form && form.dataset.currency) || '$';

  function chips() {
    return Array.from(document.querySelectorAll('input[name="splitters"]'));
  }
  function mode() {
    const el = document.querySelector('input[name="split_type"]:checked');
    return el ? el.value : 'equal';
  }
  function shareInput(id) {
    return document.querySelector('.share-input input[data-member="' + id + '"]');
  }
  function shareRow(id) {
    return document.querySelector('.share-row[data-member="' + id + '"]');
  }

  // Show a custom-share row only for members who are currently selected.
  function syncRows() {
    const isCustom = mode() === 'custom';
    if (customWrap) customWrap.hidden = !isCustom;
    chips().forEach((c) => {
      const row = shareRow(c.value);
      if (row) row.hidden = !(isCustom && c.checked);
    });
  }

  function update() {
    syncRows();
    const amount = parseFloat(amountEl.value) || 0;
    const selected = chips().filter((c) => c.checked);
    const n = selected.length;
    preview.classList.remove('over', 'ok');

    if (n === 0) {
      preview.innerHTML = 'Select at least one splitter to divide the total.';
      return;
    }

    if (mode() === 'custom') {
      let assigned = 0;
      selected.forEach((c) => {
        const inp = shareInput(c.value);
        assigned += parseFloat(inp && inp.value) || 0;
      });
      const remaining = amount - assigned;
      if (Math.abs(remaining) < 0.005) {
        preview.classList.add('ok');
        preview.innerHTML = '✓ Shares add up to <b>' + currency(amount) + '</b>. Ready to split.';
      } else if (remaining > 0) {
        preview.innerHTML = '<b>' + currency(remaining) + '</b> left to assign of ' + currency(amount) + '.';
      } else {
        preview.classList.add('over');
        preview.innerHTML = 'Over by <b>' + currency(-remaining) + '</b> — shares exceed ' + currency(amount) + '.';
      }
      return;
    }

    const per = (amount / n).toFixed(2);
    const names = selected.map((c) => c.dataset.name).join(', ');
    preview.innerHTML =
      '<b>' + currency(amount) + '</b> split across <b>' + n + '</b> ' +
      (n === 1 ? 'person' : 'people') + ' = <b>' + currency(per) +
      '</b> each<br><span style="font-size:12px">' + names + '</span>';
  }

  // Prefill empty custom inputs with the equal share when switching to custom.
  function prefillCustom() {
    const amount = parseFloat(amountEl.value) || 0;
    const selected = chips().filter((c) => c.checked);
    if (!selected.length) return;
    const per = (amount / selected.length).toFixed(2);
    selected.forEach((c) => {
      const inp = shareInput(c.value);
      if (inp && !inp.value) inp.value = amount ? per : '';
    });
  }

  function currency(v) {
    return SYMBOL + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  amountEl.addEventListener('input', update);
  chips().forEach((c) => c.addEventListener('change', update));
  document.querySelectorAll('input[name="split_type"]').forEach((r) =>
    r.addEventListener('change', () => {
      if (r.value === 'custom' && r.checked) prefillCustom();
      update();
    })
  );
  if (customWrap) {
    customWrap.addEventListener('input', update);
  }
  update();
})();

// Group icon picker — set the hidden input and highlight the chosen tile.
(function () {
  const picker = document.querySelector('.icon-picker');
  const hidden = document.getElementById('id_icon');
  if (!picker || !hidden) return;

  // Reflect any pre-set value (e.g. after a validation error).
  if (hidden.value) {
    picker.querySelectorAll('.icon-opt').forEach((b) => {
      b.classList.toggle('selected', b.dataset.icon === hidden.value);
    });
  } else {
    const first = picker.querySelector('.icon-opt');
    if (first) hidden.value = first.dataset.icon;
  }

  picker.addEventListener('click', (e) => {
    const btn = e.target.closest('.icon-opt');
    if (!btn) return;
    picker.querySelectorAll('.icon-opt').forEach((b) => b.classList.remove('selected'));
    btn.classList.add('selected');
    hidden.value = btn.dataset.icon;
  });
})();

// Copy invite link to clipboard.
(function () {
  document.querySelectorAll('.btn-copy').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      input.select();
      input.setSelectionRange(0, 99999);
      const done = () => {
        const old = btn.textContent;
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = old; btn.classList.remove('copied'); }, 1800);
      };
      if (navigator.clipboard) {
        navigator.clipboard.writeText(input.value).then(done, () => { document.execCommand('copy'); done(); });
      } else {
        document.execCommand('copy');
        done();
      }
    });
  });
})();

// Auto-dismiss toasts.
(function () {
  document.querySelectorAll('.toast').forEach((t) => {
    setTimeout(() => {
      t.style.transition = 'opacity .4s, transform .4s';
      t.style.opacity = '0';
      t.style.transform = 'translateY(-8px)';
      setTimeout(() => t.remove(), 400);
    }, 3600);
  });
})();
